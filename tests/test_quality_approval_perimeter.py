"""Exercise the quality perimeter with original Git objects and index flags."""

import os
import sys
import unittest

from tests import test_quality_required_oracle_evidence as strict
from tests import test_verify_quality as compatible


class QualityPerimeter(unittest.TestCase):
    def setUp(self):
        self.project = compatible.QualityApproval()
        self.project.setUp()
        self.addCleanup(self.project.tearDown)
        self.root = self.project.root
        self.outside = self.root / 'outside.txt'
        self.outside.write_text('approved\n', encoding='utf-8')
        self.project.policy['checks'][0]['argv'] = [sys.executable, '-c',
            "from pathlib import Path; p=Path('report.txt'); "
            "p.write_text((p.read_text() if p.exists() else '') + 'x')"]
        self.project.freeze()

    def flag(self, name, path):
        self.project.git('update-index', '--' + name, '--', path)
        expected = {'assume-unchanged': 'h', 'skip-worktree': 'S'}[name]
        self.assertEqual(self.project.git('ls-files', '-v', '--', path), f'{expected} {path}')

    def reject(self, path, *, before_checks=True):
        head = self.project.git('rev-parse', 'HEAD')
        index = self.project.git('ls-files', '-v', '--stage')
        result = self.project.run_gate()
        output = result.stdout + result.stderr
        self.assertEqual(self.project.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.project.git('ls-files', '-v', '--stage'), index)
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(path, output)
        self.assertNotIn('PASS quality', output)
        if before_checks:
            self.assertNotIn('RUN 1/2', output)
            self.assertFalse((self.root / 'report.txt').exists())
        return output

    def test_assume_unchanged_cannot_hide_an_outside_change(self):
        self.flag('assume-unchanged', 'outside.txt')
        self.outside.write_text('hidden\n', encoding='utf-8')
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), '')
        self.reject('outside.txt')
        self.assertEqual(self.outside.read_text(encoding='utf-8'), 'hidden\n')

    def test_skip_worktree_cannot_hide_an_outside_change(self):
        self.flag('skip-worktree', 'outside.txt')
        self.outside.write_text('hidden\n', encoding='utf-8')
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), '')
        self.reject('outside.txt')

    def test_combined_index_flags_cannot_hide_an_outside_change(self):
        self.flag('assume-unchanged', 'outside.txt')
        self.project.git('update-index', '--skip-worktree', '--', 'outside.txt')
        self.assertEqual(self.project.git('ls-files', '-v', '--', 'outside.txt'), 's outside.txt')
        self.outside.write_text('hidden\n', encoding='utf-8')
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), '')
        self.reject('outside.txt')

    def test_missing_flagged_outside_path_is_rejected(self):
        self.flag('assume-unchanged', 'outside.txt')
        self.outside.unlink()
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), '')
        self.reject('outside.txt')

    def test_staged_restore_cannot_hide_an_outside_commit(self):
        self.outside.write_text('committed outside change\n', encoding='utf-8')
        self.project.git('add', '--', 'outside.txt')
        self.project.git('commit', '-qm', 'Outside change')
        self.project.git('restore', '--source', self.project.ref, '--staged', '--worktree', '--', 'outside.txt')
        self.assertEqual(self.project.git('diff', '--name-only', self.project.ref, '--'), '')
        self.assertEqual(self.project.git('diff', '--name-only', self.project.ref, 'HEAD', '--'), 'outside.txt')
        self.reject('outside.txt')

    def test_staged_restore_cannot_hide_a_protected_commit(self):
        oracle = self.root / 'oracle.py'
        oracle.write_text('assert False\n', encoding='utf-8')
        self.project.git('add', '--', 'oracle.py')
        self.project.git('commit', '-qm', 'Change protected oracle')
        self.project.git('restore', '--source', self.project.ref, '--staged', '--worktree', '--', 'oracle.py')
        self.assertEqual(self.project.git('diff', '--cached', '--name-only', self.project.ref, '--'), '')
        self.reject('oracle.py')

    def test_staged_restore_cannot_hide_a_protected_mode_change(self):
        blob = self.project.git('rev-parse', self.project.ref + ':oracle.py')
        for mode in ('120000', '100755'):
            with self.subTest(mode=mode):
                self.project.git('reset', '--hard', self.project.ref)
                self.project.git('update-index', '--cacheinfo', f'{mode},{blob},oracle.py')
                self.project.git('commit', '-qm', 'Change oracle mode with identical bytes')
                self.project.git('restore', '--source', self.project.ref, '--staged', '--', 'oracle.py')
                self.assertEqual(self.project.git('rev-parse', 'HEAD:oracle.py'), blob)
                self.assertTrue(self.project.git('ls-tree', 'HEAD', '--', 'oracle.py').startswith(mode + ' '))
                self.reject('oracle.py')

    def test_protected_committed_line_endings_follow_existing_equivalence(self):
        (self.root / '.gitattributes').write_bytes(b'oracle.py -text\n')
        oracle = self.root / 'oracle.py'
        oracle.write_bytes(b'assert True\n')
        self.project.freeze()
        oracle.write_bytes(b'assert True\r\n')
        self.project.git('add', '--', 'oracle.py')
        self.project.git('commit', '-qm', 'Use CRLF in approved text oracle')
        self.project.git('restore', '--source', self.project.ref, '--staged', '--worktree', '--', 'oracle.py')
        self.assertEqual(self.project.git('diff', '--name-only', self.project.ref, 'HEAD', '--'), 'oracle.py')
        result = self.project.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'report.txt').read_text(encoding='utf-8'), 'xx')

    def test_approved_change_and_unchanged_marked_file_pass_twice(self):
        self.flag('assume-unchanged', 'outside.txt')
        self.flag('skip-worktree', 'app.py')
        (self.root / 'app.py').write_text('value = 2\n', encoding='utf-8')
        result = self.project.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'report.txt').read_text(encoding='utf-8'), 'xx')
        self.assertIn('h outside.txt', self.project.git('ls-files', '-v'))
        self.assertIn('S app.py', self.project.git('ls-files', '-v'))

    def test_other_flag_pair_and_clean_crlf_pass_twice(self):
        (self.root / '.gitattributes').write_bytes(b'outside.txt text eol=crlf\n')
        self.project.freeze()
        self.outside.write_bytes(b'approved\r\n')
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), '')
        self.flag('skip-worktree', 'outside.txt')
        self.flag('assume-unchanged', 'app.py')
        (self.root / 'app.py').write_text('value = 2\n', encoding='utf-8')
        result = self.project.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'report.txt').read_text(encoding='utf-8'), 'xx')
        self.assertIn('S outside.txt', self.project.git('ls-files', '-v'))
        self.assertIn('h app.py', self.project.git('ls-files', '-v'))

    @unittest.skipIf(os.name == 'nt', 'Git does not track worktree executable bits on Windows')
    def test_hidden_executable_change_respects_filemode(self):
        self.project.git('config', 'core.filemode', 'true')
        self.outside.chmod(0o755)
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), 'outside.txt')
        self.outside.chmod(0o644)
        self.flag('assume-unchanged', 'outside.txt')
        self.outside.chmod(0o755)
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), '')
        self.reject('outside.txt')
        self.project.git('config', 'core.filemode', 'false')
        result = self.project.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'report.txt').read_text(encoding='utf-8'), 'xx')

    def test_revert_committed_before_checks_restores_the_perimeter(self):
        self.outside.write_text('outside change\n', encoding='utf-8')
        self.project.git('add', '--', 'outside.txt')
        self.project.git('commit', '-qm', 'Outside change')
        self.project.git('revert', '--no-edit', 'HEAD')
        result = self.project.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'report.txt').read_text(encoding='utf-8'), 'xx')

    def test_clean_worktree_check_preserves_index_bytes(self):
        self.project.git('config', 'diff.autoRefreshIndex', 'true')
        index = self.root / '.git/index'
        before = index.read_bytes()
        modified = self.outside.stat().st_mtime_ns + 2_000_000_000
        os.utime(self.outside, ns=(modified, modified))
        result = self.project.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(index.read_bytes() == before, 'quality approval rewrote the index')
        self.assertEqual((self.root / 'report.txt').read_text(encoding='utf-8'), 'xx')

    def test_postcheck_rejects_an_outside_change_hidden_by_the_check(self):
        self.project.policy['checks'][0]['argv'] = [sys.executable, '-c',
            "from pathlib import Path; import subprocess; "
            "subprocess.run(['git', 'update-index', '--assume-unchanged', '--', 'outside.txt'], check=True); "
            "Path('outside.txt').write_text('changed during check', encoding='utf-8')"]
        self.project.freeze()
        result = self.project.run_gate()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn('outside.txt', output)
        self.assertIn('RUN 1/2 functional', output)
        self.assertNotIn('RUN 1/2 negative', output)
        self.assertNotIn('PASS quality', output)
        self.assertEqual(self.outside.read_text(encoding='utf-8'), 'changed during check')
        self.assertEqual(self.project.git('ls-files', '-v', '--', 'outside.txt'), 'h outside.txt')
        self.assertEqual(self.project.git('diff', '--name-only', '--', 'outside.txt'), '')


class StrictQualityPerimeter(unittest.TestCase):
    def test_generated_strict_workflow_rejects_hidden_change_before_receipts(self):
        fixture = strict.QualityEvidenceWorkflowExecution()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.fixture.entry['timeout'] = 20
        fixture.fixture.write('outside.txt', 'approved\n')
        fixture.freeze_runner()
        project = fixture.fixture
        project.git('update-index', '--assume-unchanged', '--', 'outside.txt')
        project.write('outside.txt', 'hidden\n')
        result = fixture.workflow_gate(True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('outside.txt', result.stdout + result.stderr)
        self.assertNotIn('ORACLE_REVIEW ', result.stdout)
        self.assertFalse((project.root / 'checks.txt').exists())
        self.assertEqual(project.git('ls-files', '-v', '--', 'outside.txt'), 'h outside.txt')


if __name__ == '__main__':
    unittest.main()
