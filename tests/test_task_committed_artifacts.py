"""Historical Git reads, native checkout aliases and unchanged writer boundaries."""
import hashlib
import json
import os
from pathlib import Path
import unittest
from tests import test_traceability_model as support
import task_git as journal
from task_model import TaskError
from traceability_git import build_trace
from validate_tasks import validate_range, validate_snapshot


class TaskCommittedArtifactsTests(support.RepositoryFixture):
    def alias(self, directory):
        area = Path(self.temp.name).resolve()
        source = self.root / directory
        outside = area / ('external-' + directory.replace('/', '-'))
        self.assertTrue(source.resolve().is_relative_to(self.root.resolve()))
        self.assertTrue(outside.resolve().is_relative_to(area))
        source.rename(outside)
        if os.name == 'nt':
            script = area / 'native-junction.ps1'
            script.write_text('param([string]$Link,[string]$Target)\n'
                'New-Item -ItemType Junction -Path $Link -Value $Target -ErrorAction Stop | Out-Null\n',
                encoding='utf-8')
            p = support.command(area, ['powershell.exe', '-NoProfile', '-NonInteractive',
                '-ExecutionPolicy', 'Bypass', '-File', str(script), '-Link', str(source), '-Target', str(outside)])
            self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
            self.assertTrue(source.lstat().st_file_attributes & 0x400)
        else:
            source.symlink_to(outside, target_is_directory=True)
            self.assertTrue(source.is_symlink())
        self.addCleanup(self.remove_alias, source)
        name, text = {
            'src': ('value.py', "raise RuntimeError('external product must never run')\n"),
            'tests': ('test_value.py', "from pathlib import Path\nPath(__file__).with_name('executed').write_text('bad')\nraise RuntimeError('external oracle must never run')\n"),
            'knowledge/contracts': ('value.md', 'invalid live contract: use the committed blob\n'),
        }[directory]
        support.write(outside, name, text)
        return outside

    @staticmethod
    def remove_alias(path):
        if path.is_symlink():
            path.unlink()
        elif os.name == 'nt' and path.exists() and path.lstat().st_file_attributes & 0x400:
            path.rmdir()

    @staticmethod
    def files(root):
        return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in root.rglob('*') if p.is_file()}

    def task(self, ref=None):
        return journal.read_tasks(self.root, ref or self.refs['closed'])['TASK-001']

    def trace(self, ref='main'):
        return build_trace(self.root, ref, 'quality/traceability.json', require_verified=True)

    def queries(self, ref='main'):
        with journal.object_cache():
            return (validate_snapshot(self.root, ref),
                    validate_range(self.root, self.task()['branch_base'], ref), self.trace(ref))

    def snapshot_alias(self, directory):
        before = self.queries()
        self.assertEqual(before[0], [])
        self.assertEqual(before[1], [])
        self.assertTrue(before[2]['complete'])
        outside = self.alias(directory)
        canary = self.files(outside)
        self.assertEqual(self.queries(), before)
        self.assertEqual(self.files(outside), canary)

    def ready_checkout(self):
        ready = self.task()['branch_base']
        support.git(self.root, 'switch', '-q', '-c', 'ready-history', ready)
        self.assertEqual(validate_snapshot(self.root, 'HEAD'), [])
        return ready

    def commit_index(self, message):
        support.git(self.root, 'commit', '-qm', message)
        return support.git(self.root, 'rev-parse', 'HEAD')

    def git_link_mode(self, name):
        self.ready_checkout()
        blob = support.git(self.root, 'rev-parse', 'HEAD:' + name)
        support.git(self.root, 'update-index', '--cacheinfo', '120000,'+blob+','+name)
        self.commit_index('Git link mode with unchanged file payload')
        self.assertTrue((self.root/name).is_file())
        self.assertFalse((self.root/name).is_symlink())
        self.assertTrue(support.git(self.root, 'ls-tree', 'HEAD', '--', name).startswith('120000'))
        findings = validate_snapshot(self.root, 'HEAD')
        self.assertTrue(findings, 'Git link mode must fail despite a regular live file')
        self.assertIn('TASK_PATH', '\n'.join(findings))

    def writer_rejects(self, directory):
        metadata = journal.contract_metadata(self.root, self.task(), self.refs['closed'])
        self.assertEqual(metadata['target'], 'src/value.py')
        outside = self.alias(directory)
        before = self.files(outside)
        with self.assertRaisesRegex(TaskError, 'TASK_PATH'):
            journal.contract_metadata(self.root, self.task(), self.refs['closed'])
        self.assertEqual(self.files(outside), before)

    def test_snapshot_ignores_uncommitted_target_directory_alias(self):
        self.snapshot_alias('src')

    def test_snapshot_ignores_uncommitted_oracle_directory_alias(self):
        self.snapshot_alias('tests')

    def test_snapshot_ignores_uncommitted_contract_directory_alias(self):
        self.snapshot_alias('knowledge/contracts')

    def test_range_with_all_checkout_aliases_preserves_original_refs_and_evidence(self):
        before = self.queries()
        self.assertTrue(before[2]['complete'])
        outside = [self.alias(name) for name in ('src','tests','knowledge/contracts')]
        canaries = [self.files(path) for path in outside]
        after = self.queries()
        self.assertEqual(after, before)
        link = after[2]['requirements'][0]['links'][0]
        self.assertEqual(link['approved_ref'], self.refs['approved'])
        self.assertEqual(link['tested_commit'], self.refs['tested'])
        self.assertEqual(link['branch_tip'], self.refs['tip'])
        self.assertEqual([self.files(path) for path in outside], canaries)

    def test_cli_json_and_markdown_preserve_index_refs_branch_and_canaries(self):
        expected = self.trace()
        outside = [self.alias(name) for name in ('src','tests','knowledge/contracts')]
        canaries = [self.files(path) for path in outside]
        support.git(self.root, 'status', '--porcelain=v1')
        index = (self.root/'.git/index').read_bytes()
        refs = support.git(self.root, 'show-ref')
        branch = support.git(self.root, 'branch', '--show-current')
        p = self.cli('--require-verified', cwd=Path(self.temp.name))
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertEqual(self.json_result(p), expected)
        p = self.cli('--require-verified', '--format', 'markdown')
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        for value in (self.refs['tested'], 'REQ-001', 'TASK-001', 'verified'):
            self.assertIn(value, p.stdout)
        self.assertEqual((self.root/'.git/index').read_bytes(), index)
        self.assertEqual(support.git(self.root, 'show-ref'), refs)
        self.assertEqual(support.git(self.root, 'branch', '--show-current'), branch)
        self.assertEqual([self.files(path) for path in outside], canaries)

    def test_other_branch_with_committed_git_link_still_queries_historical_main(self):
        expected = self.trace()
        support.git(self.root, 'switch', '-q', '-c', 'other-layout')
        outside = self.alias('src')
        payload = support.git(self.root, 'hash-object', '-w', '--stdin', input='../../external/value.py\n')
        support.git(self.root, 'update-index', '--cacheinfo', '120000,'+payload+',src/value.py')
        self.commit_index('Different branch with a committed Git symlink')
        before = support.git(self.root, 'status', '--porcelain=v1')
        canary = self.files(outside)
        p = self.cli('--require-verified')
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertEqual(self.json_result(p), expected)
        self.assertEqual(support.git(self.root, 'branch', '--show-current'), 'other-layout')
        self.assertEqual(support.git(self.root, 'status', '--porcelain=v1'), before)
        self.assertEqual(self.files(outside), canary)

    def test_absent_checkout_artifacts_are_not_materialized(self):
        before = self.queries()
        area = Path(self.temp.name)
        for name in ('src','tests','knowledge/contracts'):
            destination = area/('removed-'+name.replace('/','-'))
            self.assertTrue(destination.resolve().is_relative_to(area.resolve()))
            (self.root/name).rename(destination)
        self.assertEqual(self.queries(), before)
        self.assertTrue(before[2]['complete'])
        self.assertFalse(any((self.root/name).exists() for name in ('src','tests','knowledge/contracts')))

    def test_default_writer_guard_still_rejects_target_alias(self):
        self.writer_rejects('src')

    def test_default_writer_guard_still_rejects_oracle_alias(self):
        self.writer_rejects('tests')

    def test_default_writer_guard_still_rejects_contract_alias(self):
        self.writer_rejects('knowledge/contracts')

    def test_committed_contract_git_link_is_rejected_despite_regular_checkout(self):
        self.git_link_mode('knowledge/contracts/value.md')

    def test_committed_oracle_git_link_is_rejected_despite_regular_checkout(self):
        self.git_link_mode('tests/test_value.py')

    def test_committed_target_git_link_is_rejected_despite_regular_checkout(self):
        self.git_link_mode('src/value.py')

    def test_missing_committed_target_cannot_be_replaced_by_a_live_file(self):
        self.ready_checkout()
        support.git(self.root, 'update-index', '--force-remove', '--', 'src/value.py')
        self.commit_index('Target absent in Git but retained in checkout')
        self.assertTrue((self.root/'src/value.py').is_file())
        findings = validate_snapshot(self.root, 'HEAD')
        self.assertTrue(findings, 'The committed target must exist')
        self.assertIn('TASK_PATH', '\n'.join(findings))

    def test_approved_metadata_path_escape_is_still_rejected(self):
        self.ready_checkout()
        contract_path = 'knowledge/contracts/value.md'
        contract = (self.root/contract_path).read_text(encoding='utf-8')
        node_path = 'knowledge/tasks/TASK-001.md'
        original_node = (self.root/node_path).read_text(encoding='utf-8')
        old_ref = self.task()['approved_ref']
        for target in ('../outside.py', '/absolute.py', 'C:/outside.py', 'src\\outside.py'):
            with self.subTest(target=target):
                support.write(self.root, contract_path, contract.replace('target: src/value.py', 'target: '+target))
                approved = support.commit(self.root, 'Synthetic approved fixture with unsafe target')
                support.write(self.root, node_path, original_node.replace(old_ref, approved))
                support.commit(self.root, 'Select explicit fixture approval for unsafe metadata')
                findings = validate_snapshot(self.root, 'HEAD')
                self.assertTrue(findings)
                self.assertIn('TASK_PATH', '\n'.join(findings))

    def test_unapproved_oracle_error_is_unchanged_by_checkout_alias(self):
        self.ready_checkout()
        support.write(self.root, 'tests/test_value.py', support.ORACLE+'\n# unapproved oracle\n')
        support.commit(self.root, 'Unapproved oracle change')
        expected = validate_snapshot(self.root, 'HEAD')
        self.assertIn('TASK_APPROVAL', '\n'.join(expected))
        self.alias('tests')
        self.assertEqual(validate_snapshot(self.root, 'HEAD'), expected)

    def test_adulterated_evidence_error_survives_checkout_aliases(self):
        task = self.task()
        artifact = json.loads((self.root/task['evidence']).read_text(encoding='utf-8'))
        artifact['passed_tests'] = 0
        raw = support.dump(artifact)
        support.write(self.root, task['evidence'], raw)
        path = 'knowledge/tasks/TASK-001.md'
        node = (self.root/path).read_text(encoding='utf-8')
        support.write(self.root, path, node.replace(task['evidence_sha256'], hashlib.sha256(raw.encode('utf-8')).hexdigest()))
        support.commit(self.root, 'Tampered proof with internally consistent artifact digest')
        expected = self.queries()
        self.assertIn('TASK_EVIDENCE', '\n'.join(expected[0]))
        self.assertFalse(expected[2]['ok'])
        self.alias('src')
        self.assertEqual(self.queries(), expected)

    def test_invalid_intermediate_history_cannot_hide_behind_aliases(self):
        path = 'knowledge/tasks/TASK-001.md'
        node = (self.root/path).read_text(encoding='utf-8')
        support.write(self.root, path, node.replace("status: 'done'", "status: 'blocked'"))
        support.commit(self.root, 'Illegal intermediate completed-task mutation')
        support.write(self.root, path, node)
        support.commit(self.root, 'Restore valid tip without hiding illegal history')
        expected = self.queries()
        self.assertTrue(expected[1])
        self.assertFalse(expected[2]['ok'])
        self.alias('src')
        self.assertEqual(self.queries(), expected)

    def test_stale_report_keeps_historical_evidence_with_checkout_alias(self):
        support.write(self.root, 'src/value.py', support.IMPLEMENTATION+'\n# later committed version\n')
        support.commit(self.root, 'Different current source after task closure')
        expected = self.trace()
        self.assertFalse(expected['ok'])
        self.assertEqual(expected['requirements'][0]['state'], 'stale')
        self.assertTrue(expected['requirements'][0]['links'][0]['historical_verified'])
        self.alias('src')
        self.assertEqual(self.trace(), expected)


if __name__ == '__main__':
    unittest.main()
