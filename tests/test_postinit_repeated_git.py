"""Real Git comparisons and process budgets for repeated post-init reads."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests import test_generated_task_evidence as generated
from tests import test_task_history_read_cost as graph
from tests import test_task_perimeter_stage_batch as fixture
from tests.test_fixture_preparation import configure_git
import task_git as journal


class PerimeterMergeRead(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.PerimeterStageBatchTests('runTest')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def test_cold_merge_scope_uses_one_git_process_in_both_formats(self):
        product = 'src/with space\ttab\nline-\u00f1.py'
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm):
                root, refs = self.fixture.repository(algorithm, product=product, merge_only=True)
                before = fixture.state(root)
                changed, commands = self.fixture.observe(root, refs)
                self.assertEqual(changed, {product, 'outside-transient.txt', 'integration-only.txt'})
                self.assertNotIn('docs/main-only.txt', changed)
                self.assertEqual(fixture.state(root), before)
                self.assertEqual(len(commands), 1, commands)

    def test_merge_without_first_parent_changes_preserves_owned_history(self):
        root, refs = self.fixture.repository('sha1', merge_only=True)
        tree = graph.git(root, 'rev-parse', refs['main'] + '^{tree}')
        refs['tested'] = graph.git(root, 'commit-tree', tree, '-p', refs['main'],
                                   '-p', refs['tip'], '-m', 'Merge with unchanged first-parent tree')
        before = fixture.state(root)
        self.assertEqual(graph.git(root, 'diff', '--name-only', refs['main'], refs['tested']), '')
        context = journal._PerimeterContext(refs['base'], refs['tip'], refs['tested'])
        with journal.object_cache():
            changed = journal._perimeter_paths(root, context)
        self.assertEqual(changed, {'src/value.py', 'outside-transient.txt'})
        self.assertEqual(fixture.state(root), before)

    def test_merge_replacement_reloads_first_parent_diff_and_recovers(self):
        root, refs = self.fixture.repository('sha1', merge_only=True)
        initial, _ = self.fixture.observe(root, refs)
        self.assertIn('integration-only.txt', initial)
        tree = graph.git(root, 'rev-parse', refs['main'] + '^{tree}')
        replacement = graph.git(root, 'commit-tree', tree, '-p', refs['main'],
                                '-p', refs['tip'], '-m', 'Replacement keeps the first-parent tree')
        graph.git(root, 'replace', refs['tested'], replacement)
        before = fixture.state(root)
        changed, _ = self.fixture.observe(root, refs)
        self.assertEqual(changed, {'src/value.py', 'outside-transient.txt'})
        self.assertEqual(fixture.state(root), before)
        graph.git(root, 'replace', '-d', refs['tested'])
        restored, _ = self.fixture.observe(root, refs)
        self.assertEqual(restored, initial)


class FixtureSnapshotRead(unittest.TestCase):
    def setUp(self):
        self.area = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='kdd-snapshot-')))
        self.sequence = 0

    def repository(self, algorithm='sha1', committed=True):
        self.sequence += 1
        root = self.area / ('repo-' + str(self.sequence))
        root.mkdir()
        project = generated.TaskProject(root, initialize=False)
        project.git('init', '-q', '-b', 'main', '--object-format=' + algorithm)
        configure_git(root, {'user.name': 'Snapshot fixture', 'user.email': 'snapshot@example.invalid',
                            'core.autocrlf': 'false'}, ephemeral=True)
        project.git('config', 'core.quotePath', 'false')
        if committed:
            project.write('# old \u00f1.txt', 'original\n')
            project.commit('Snapshot baseline')
        return project

    def observe(self, project):
        trace = self.area / ('git-' + str(self.sequence) + '.jsonl')
        with patch.dict(project.env, {'GIT_TRACE2_EVENT': str(trace)}):
            snapshot = project.snapshot()
        records = [json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()]
        commands = [record['argv'] for record in records if record.get('event') == 'start']
        return snapshot, commands

    def test_native_head_and_status_share_one_read_in_both_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm):
                project = self.repository(algorithm)
                before = fixture.state(project.root)
                snapshot, commands = self.observe(project)
                self.assertEqual(snapshot, {'head': before[0], 'branches': before[1],
                                            'status': '', 'tree': project.git('write-tree')})
                self.assertEqual(fixture.state(project.root), before)
                self.assertEqual(len(commands), 3, commands)

    def test_new_head_and_branch_are_detected_without_changes_to_the_tree(self):
        project = self.repository()
        initial = project.snapshot()
        project.git('commit', '--allow-empty', '-qm', 'Advance HEAD without tree changes')
        project.git('branch', 'another-local-ref')
        actual = project.snapshot()
        self.assertEqual(actual['head'], project.git('rev-parse', 'HEAD'))
        self.assertNotEqual(actual['head'], initial['head'])
        self.assertIn('refs/heads/another-local-ref', actual['branches'])
        self.assertEqual(actual['tree'], initial['tree'])
        self.assertEqual(actual['status'], initial['status'])

    def test_snapshot_keeps_staged_reversal_renames_and_untracked_paths(self):
        project = self.repository()
        initial = project.snapshot()
        project.write('# old \u00f1.txt', 'staged edit\n')
        project.git('add', '--', '# old \u00f1.txt')
        project.write('# old \u00f1.txt', 'original\n')
        staged = project.snapshot()
        self.assertNotEqual(staged['status'], initial['status'])
        self.assertNotEqual(staged['tree'], initial['tree'])
        project.git('reset', '--hard', '-q', 'HEAD')
        project.git('mv', '--', '# old \u00f1.txt', 'new \u00f1.txt')
        project.write('new untracked.txt', 'not staged\n')
        renamed = project.snapshot()
        expected = project.git('status', '--porcelain=v2')
        self.assertIn('# old \u00f1.txt', expected)
        self.assertIn('new untracked.txt', expected)
        self.assertEqual(renamed['status'], expected)
        self.assertEqual(renamed['head'], initial['head'])

    def test_unborn_repository_still_reports_real_git_failure(self):
        project = self.repository(committed=False)
        with self.assertRaises(subprocess.CalledProcessError):
            project.snapshot()


if __name__ == '__main__':
    unittest.main()
