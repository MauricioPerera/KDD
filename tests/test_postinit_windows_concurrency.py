"""Native post-init capacity with real processes, discovery and inventory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'scripts'
BARRIER = """import os
from pathlib import Path
import time
import unittest

class ConcurrentModule(unittest.TestCase):
    def test_reaches_every_other_module(self):
        arrivals = Path('arrivals')
        name = Path(__file__).stem
        (arrivals / name).write_text(str(os.getpid()), encoding='ascii')
        deadline = time.monotonic() + 35
        while len(list(arrivals.iterdir())) < 10 and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertEqual(len(list(arrivals.iterdir())), 10)
"""


class PostInitWindowsConcurrency(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(
            prefix='kdd-postinit-workers-')))
        self.tests = self.root / 'tests'
        self.tests.mkdir()
        scripts = self.root / 'scripts'
        scripts.mkdir()
        for name in ('init_post_apply_suite.py', 'run_test_suite.py', 'process_tree.py'):
            shutil.copyfile(SOURCE / name, scripts / name)
        self.report = self.root / 'suite.json'

    def run_script(self, name, *args):
        return subprocess.run(
            [sys.executable, '-X', 'utf8', 'scripts/' + name, *args],
            cwd=self.root, env=dict(os.environ, PYTHONUTF8='1'),
            capture_output=True, encoding='utf-8', timeout=100)

    def check_pass(self, result, count, workers):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(self.report.read_text(encoding='utf-8'))
        self.assertTrue(report['ok'])
        self.assertEqual(report['workers'], workers)
        self.assertEqual(report['tests_run'], count)
        self.assertEqual(report['expected_ids'], report['executed_ids'])
        self.assertEqual(len(set(report['executed_ids'])), count)
        self.assertEqual(report['fixture_omitted_ids'], [])
        self.assertEqual(report['skipped'], [])
        return report

    def test_ten_independent_workers_can_meet_the_real_barrier(self):
        arrivals = self.root / 'arrivals'
        arrivals.mkdir()
        for index in range(10):
            (self.tests / ('test_barrier_%02d.py' % index)).write_text(BARRIER, encoding='utf-8')
        result = self.run_script('run_test_suite.py', '--workers', '10',
                                 '--report-json', str(self.report))
        report = self.check_pass(result, 10, 10)
        pids = {int(path.read_text(encoding='ascii')) for path in arrivals.iterdir()}
        self.assertEqual(len(pids), 10)
        self.assertEqual(pids, {module['pid'] for module in report['modules']})

    def test_eleven_workers_fail_before_discovery(self):
        (self.tests / 'test_imported.py').write_text(
            'from pathlib import Path\nPath("imported").touch()\n', encoding='utf-8')
        result = self.run_script('run_test_suite.py', '--workers', '11',
                                 '--report-json', str(self.report))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('workers', result.stderr)
        self.assertFalse((self.root / 'imported').exists())
        self.assertFalse(self.report.exists())

    def test_initialized_launcher_retains_the_native_profile(self):
        (self.tests / 'test_one.py').write_text(
            'import unittest\nclass One(unittest.TestCase):\n'
            '    def test_one(self): self.assertTrue(True)\n', encoding='utf-8')
        result = self.run_script('init_post_apply_suite.py', '--repo-root',
                                 str(self.root), '--report-json', str(self.report))
        self.check_pass(result, 1, 10 if os.name == 'nt' else 4)


if __name__ == '__main__':
    unittest.main()
