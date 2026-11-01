"""Real post-init suite processes and inventory for the CI worker profile."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PostApplyProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kdd init profile ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'tests').mkdir()
        for name in ('run_test_suite.py', 'process_tree.py'):
            shutil.copyfile(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        (self.root / 'tests/test_first.py').write_text(
            'import unittest\nclass First(unittest.TestCase):\n def test_a(self): self.assertEqual(2+2,4)\n', encoding='utf-8')
        (self.root / 'tests/test_second.py').write_text(
            'import unittest\nclass Second(unittest.TestCase):\n def test_b(self): self.assertTrue(True)\n', encoding='utf-8')
        self.report = self.root.parent / (self.root.name + '-report.json')
        self.addCleanup(self.report.unlink, missing_ok=True)

    def run_profile(self):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/init_post_apply_suite.py'),
                               '--repo-root', str(self.root), '--report-json', str(self.report)],
                              cwd=self.root, capture_output=True, text=True, encoding='utf-8', timeout=120)

    def test_real_child_runs_complete_inventory_with_native_profile(self):
        result = self.run_profile()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(self.report.read_text(encoding='utf-8'))
        self.assertTrue(report['ok'])
        self.assertEqual(report['workers'], 6 if os.name == 'nt' else 4)
        self.assertEqual(report['tests_run'], 2)
        self.assertEqual(report['expected_ids'], report['executed_ids'])
        self.assertEqual(report['skipped'], [])
        self.assertEqual(report['fixture_omitted_ids'], [])

    def test_real_failing_child_cannot_be_reported_as_success(self):
        (self.root / 'tests/test_second.py').write_text(
            'import unittest\nclass Second(unittest.TestCase):\n def test_b(self): self.fail("synthetic")\n', encoding='utf-8')
        result = self.run_profile()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.report.exists(), result.stdout + result.stderr)
        report = json.loads(self.report.read_text(encoding='utf-8'))
        self.assertFalse(report['ok'])
        self.assertTrue(report['failures'])
        self.assertEqual(report['tests_run'], 2)

    def test_preexisting_report_is_not_reused(self):
        self.report.write_text('{"ok":true}', encoding='utf-8')
        result = self.run_profile()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.report.read_text(encoding='utf-8'), '{"ok":true}')


if __name__ == '__main__':
    unittest.main()
