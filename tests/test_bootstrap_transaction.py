"""Real IO errors and recovery, including the two public bootstrap entries."""
import importlib
import unittest
from tests import test_bootstrap_boundary as support


def engine():
    return importlib.import_module('scripts.bootstrap_transaction').filesystem_transaction


@unittest.skipUnless(support.IS_TEMPLATE, 'template-only bootstrap integration: project already initialized')
class BootstrapTransaction(support.SandboxFixture):
    def invoke(self, paths, action, expected=None):
        observed = None
        try:
            with engine()(self.root, paths):
                action()
        except (OSError, ValueError) as exc:
            observed = exc
        except Exception as exc:
            self.fail('Transaction could not execute its integration: ' + repr(exc))
        if expected is None:
            self.assertIsNone(observed, str(observed))
        else:
            self.assertIsInstance(observed, expected)
        return observed

    def failing_write(self):
        # A directory cannot be opened as a regular file on either OS.
        (self.root / 'blocked-write').write_bytes(b'cannot overwrite a directory')

    def small_files(self):
        (self.root / 'a.txt').write_bytes(b'old A\n')
        (self.root / 'b.txt').write_bytes(b'old B\n')
        (self.root / 'unmanaged.txt').write_bytes(b'keep user data\n')
        (self.root / 'blocked-write').mkdir()

    def test_guide_directory_is_preflighted_and_correctable(self):
        guide = self.root / 'KDD-START-HERE.md'
        guide.mkdir()
        with self.assertRaises(OSError):
            guide.write_text('real failed write', encoding='utf-8')
        before = support.snapshot(self.root)
        p = self.cli('bootstrap_project.py')
        self.assertNotEqual(p.returncode, 0)
        self.unchanged(before, self.root, 'failed bootstrap')
        guide.rmdir()
        p = self.cli('bootstrap_project.py')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(guide.is_file())

    def test_invalid_index_does_not_leave_deleted_template(self):
        (self.root / 'knowledge/index.md').write_bytes(b'\xffinvalid UTF-8\n')
        before = support.snapshot(self.root)
        p = self.cli()
        self.assertNotEqual(p.returncode, 0)
        self.unchanged(before, self.root, 'invalid metadata input')

    def test_real_io_failure_restores_deletes_writes_and_new_file(self):
        self.small_files()
        before = support.snapshot(self.root)
        def action():
            (self.root / 'a.txt').write_bytes(b'changed A\n')
            (self.root / 'b.txt').unlink()
            (self.root / 'new.txt').write_bytes(b'partial output\n')
            self.failing_write()
        self.invoke(['a.txt', 'b.txt', 'new.txt'], action, OSError)
        self.unchanged(before, self.root, 'rolled-back plan')

    def test_success_keeps_managed_changes_and_unmanaged_data(self):
        self.small_files()
        def action():
            (self.root / 'a.txt').write_bytes(b'accepted\n')
            (self.root / 'b.txt').unlink()
        self.invoke(['a.txt', 'b.txt'], action)
        self.assertEqual((self.root / 'a.txt').read_bytes(), b'accepted\n')
        self.assertFalse((self.root / 'b.txt').exists())
        self.assertEqual((self.root / 'unmanaged.txt').read_bytes(), b'keep user data\n')
        self.assertFalse(any(p.name.startswith('.kdd-') for p in self.root.iterdir()))

    def test_failed_new_output_removes_only_own_empty_directories(self):
        self.small_files()
        before = support.snapshot(self.root)
        def action():
            path = self.root / 'generated/nested/output.txt'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'partial output\n')
            self.failing_write()
        self.invoke(['generated/nested/output.txt'], action, OSError)
        self.unchanged(before, self.root, 'new output rollback')

    def test_outer_failure_restores_successful_inner_region(self):
        self.small_files()
        before = support.snapshot(self.root)
        def action():
            (self.root / 'a.txt').write_bytes(b'outer output\n')
            with engine()(self.root, ['b.txt']):
                (self.root / 'b.txt').unlink()
            self.failing_write()
        self.invoke(['a.txt'], action, OSError)
        self.unchanged(before, self.root, 'nested rollback')

    def test_preflight_checks_entire_plan_before_callback(self):
        self.small_files()
        called = []
        error = self.invoke(['a.txt', 'blocked-write'], lambda: called.append(True), ValueError)
        self.assertIn('BOOTSTRAP_PATH', str(error))
        self.assertEqual(called, [])
        self.assertEqual((self.root / 'a.txt').read_bytes(), b'old A\n')

    def test_relative_escape_is_rejected_before_callback(self):
        outside = self.area / 'outside.txt'
        outside.write_bytes(b'outside canary\n')
        called = []
        error = self.invoke(['../outside.txt'], lambda: called.append(True), ValueError)
        self.assertIn('BOOTSTRAP_PATH', str(error))
        self.assertEqual(called, [])
        self.assertEqual(outside.read_bytes(), b'outside canary\n')

    def test_transaction_state_is_reset_before_retry(self):
        self.small_files()
        before = support.snapshot(self.root)
        def failed():
            (self.root / 'a.txt').unlink()
            self.failing_write()
        self.invoke(['a.txt'], failed, OSError)
        self.unchanged(before, self.root, 'first attempt')
        self.invoke(['b.txt'], lambda: (self.root / 'b.txt').write_bytes(b'second accepted\n'))
        self.assertEqual((self.root / 'a.txt').read_bytes(), b'old A\n')
        self.assertEqual((self.root / 'b.txt').read_bytes(), b'second accepted\n')


if __name__ == '__main__':
    unittest.main()
