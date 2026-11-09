"""Real Git evidence that projection parses the observed task-node bytes."""
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import test_traceability_contract_batch as fixture
from tests import test_traceability_model as support
import task_git as journal
import traceability_git as projection_module
from task_model import TaskError, new_task, render_task
from traceability_git import _Projection, build_trace

NODE = 'knowledge/tasks/TASK-001.md'


class TraceTaskNodeObservation(unittest.TestCase):
    def setUp(self):
        self.area = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='kdd-observed-nodes-')))

    def repository(self, algorithm='sha1', name=NODE):
        repo = fixture.RealRepository(self.area / algorithm, algorithm)
        task = new_task('TASK-001', 'Observed task', 'Real Git fixture', repo.contract)
        repo.write(name, render_task(task))
        repo.commit('Commit regular task')
        return repo, task

    def projection(self, repo, revision=None):
        return _Projection(repo.root, revision or repo.revision, 'unused.json')

    def test_cold_regular_node_uses_two_real_git_reads_in_both_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm), journal.object_cache():
                repo, task = self.repository(algorithm)
                before = repo.git('show-ref'), (repo.root / '.git/index').read_bytes()
                self.assertTrue(journal._native_oid(repo.root, repo.revision))
                trace = self.area / (algorithm + '-git.jsonl')
                with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
                    observed = self.projection(repo).tasks()
                records = [json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()]
                starts = [record['argv'] for record in records if record.get('event') == 'start']
                self.assertEqual(observed, {'TASK-001': task})
                self.assertEqual((repo.git('show-ref'), (repo.root / '.git/index').read_bytes()), before)
                self.assertEqual(len(starts), 2, starts)
                self.assertTrue(any('ls-tree' in argv for argv in starts))
                self.assertTrue(any('cat-file' in argv for argv in starts))

    def test_warm_journal_cannot_hide_invalid_observed_replacement(self):
        repo, task = self.repository()
        original = repo.revision
        repo.write(NODE, render_task(task).replace("status: 'backlog'", "status: 'invalid'"))
        repo.commit('Commit invalid node to use as replacement')
        with journal.object_cache():
            self.assertEqual(journal.read_tasks(repo.root, original), {'TASK-001': task})
            repo.git('replace', original, repo.revision)
            self.assertIn("status: 'invalid'", repo.git('show', original + ':' + NODE))
            with self.assertRaisesRegex(TaskError, 'TASK_'):
                self.projection(repo, original).tasks()
            repo.git('replace', '-d', original)
            self.assertEqual(self.projection(repo, original).tasks(), {'TASK-001': task})

    def test_invalid_utf8_replacement_cannot_reuse_warm_valid_node(self):
        repo, task = self.repository()
        original = repo.revision
        (repo.root / NODE).write_bytes(b'\xffinvalid UTF-8\n')
        repo.commit('Commit invalid UTF-8 for the replacement')
        with journal.object_cache():
            self.assertEqual(journal.read_tasks(repo.root, original), {'TASK-001': task})
            repo.git('replace', original, repo.revision)
            self.assertNotEqual(repo.git('rev-parse', original + ':' + NODE),
                                repo.git('--no-replace-objects', 'rev-parse', original + ':' + NODE))
            with self.assertRaisesRegex(TaskError, 'TASK_GIT:'):
                self.projection(repo, original).tasks()
            repo.git('replace', '-d', original)
            self.assertEqual(self.projection(repo, original).tasks(), {'TASK-001': task})

    def test_fallback_reads_the_current_regular_blob_despite_warm_journal(self):
        repo, task = self.repository()
        original = repo.revision
        updated = dict(task, title='Changed by a real Git replacement')
        repo.write(NODE, render_task(updated))
        repo.commit('Commit valid replacement node')
        with journal.object_cache():
            self.assertEqual(journal.read_tasks(repo.root, original), {'TASK-001': task})
            repo.git('replace', original, repo.revision)
            with patch.object(journal, '_read_metadata', return_value=False):
                self.assertEqual(self.projection(repo, original).tasks(), {'TASK-001': updated})
            repo.git('replace', '-d', original)
            self.assertEqual(self.projection(repo, original).tasks(), {'TASK-001': task})

    def test_later_git_link_is_reported_before_first_node_parse_error(self):
        repo, task = self.repository()
        second = 'knowledge/tasks/TASK-002.md'
        repo.write(NODE, render_task(task).replace("status: 'backlog'", "status: 'invalid'"))
        repo.write(second, render_task(new_task('TASK-002', 'Second', 'Mode error', repo.contract)))
        repo.commit('Commit first invalid node and second regular node')
        repo.link_in_index(second)
        with journal.object_cache(), self.assertRaisesRegex(ValueError,
                'expected a regular Git blob: knowledge/tasks/TASK-002.md'):
            self.projection(repo).tasks()

    def test_git_link_is_rejected_as_an_invalid_node(self):
        repo, _ = self.repository()
        repo.link_in_index(NODE)
        with journal.object_cache(), self.assertRaisesRegex(ValueError, 'expected a regular Git blob'):
            self.projection(repo).tasks()

    def test_nested_node_keeps_canonical_path_rejection(self):
        repo, _ = self.repository(name='knowledge/tasks/nested/TASK-001.md')
        with journal.object_cache(), self.assertRaisesRegex(TaskError, 'nested task records'):
            self.projection(repo).tasks()


class TraceProjectedJournal(support.RepositoryFixture):
    def forged_revision(self):
        original = self.refs['closed']
        node = self.root / NODE
        actual = journal.read_tasks(self.root, original)['TASK-001']['evidence_sha256']
        node.write_text(node.read_text(encoding='utf-8').replace(actual, '0' * 64), encoding='utf-8')
        support.git(self.root, 'add', '--', NODE)
        tree = support.git(self.root, 'write-tree')
        parents = support.git(self.root, 'show', '-s', '--format=%P', original).split()
        args = ['commit-tree', tree]
        for parent in parents:
            args += ['-p', parent]
        replaced = support.git(self.root, *args, '-m', 'Replacement carries a forged evidence digest')
        support.git(self.root, 'reset', '--hard', original)
        return original, replaced

    def test_projection_cannot_use_replaced_digest_under_a_different_audited_node(self):
        original, replaced = self.forged_revision()
        manifest = 'quality/traceability.json'
        with journal.object_cache():
            before = build_trace(self.root, original, manifest, require_verified=True)
            self.assertTrue(before['complete'], before)
            support.git(self.root, 'replace', original, replaced)
            self.assertIn('0' * 64, support.git(self.root, 'show', original + ':' + NODE))
            report = build_trace(self.root, original, manifest, require_verified=True)
            self.assertFalse(report['complete'], report)
            self.assertTrue(any(finding['code'] == 'TRACE_JOURNAL' for finding in report['findings']), report)
            self.assertFalse(any(link['state'] == 'verified' for row in report['requirements']
                                 for link in row['links']), report)
            support.git(self.root, 'replace', '-d', original)
        self.assertEqual(build_trace(self.root, original, manifest, require_verified=True), before)


    def test_new_repository_at_same_path_cannot_substitute_the_audited_node(self):
        original, replaced = self.forged_revision()
        manifest = 'quality/traceability.json'
        real_validate_range = projection_module.validate_range
        witnesses = []

        def swap_after_audit(*args):
            findings = real_validate_range(*args)
            previous = self.root.stat()
            moved = self.root.with_name('original-case-repo')
            self.root.rename(moved)
            shutil.copytree(moved, self.root)
            current = self.root.stat()
            self.assertNotEqual((previous.st_dev, previous.st_ino, previous.st_ctime_ns),
                                (current.st_dev, current.st_ino, current.st_ctime_ns))
            self.assertIn('0' * 64, support.git(self.root, 'show', original + ':' + NODE))
            witnesses.append(True)
            return findings

        with journal.object_cache():
            before = build_trace(self.root, original, manifest, require_verified=True)
            self.assertTrue(before['complete'], before)
            support.git(self.root, 'replace', original, replaced)
            with patch.object(projection_module, 'validate_range', side_effect=swap_after_audit):
                report = build_trace(self.root, original, manifest, require_verified=True)
        self.assertEqual(witnesses, [True])
        self.assertFalse(report['complete'], report)
        self.assertTrue(any(finding['code'] == 'TRACE_JOURNAL' for finding in report['findings']), report)
        self.assertFalse(any(link['state'] == 'verified' for row in report['requirements']
                             for link in row['links']), report)


if __name__ == '__main__':
    unittest.main()
