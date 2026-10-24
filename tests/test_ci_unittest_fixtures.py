"""Compare real unittest execution and KDD, including fixture omissions."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/run_test_suite.py'


class UnittestFixtures(unittest.TestCase):
    def setUp(self):
        case = tempfile.TemporaryDirectory(prefix='kdd fixtures ')
        self.addCleanup(case.cleanup)
        self.root = Path(case.name)
        self.tests = self.root / 'tests'
        self.tests.mkdir()

    def source(self, source, name='test_fixture.py'):
        (self.tests / name).write_text(source, encoding='utf-8')

    def execute(self, workers):
        report = self.root / ('report-' + str(workers) + '.json')
        proc = subprocess.run([sys.executable, str(RUNNER), '--start-directory', 'tests',
                               '--workers', str(workers), '--report-json', str(report)],
                              cwd=self.root, capture_output=True, text=True, encoding='utf-8', timeout=45)
        self.assertTrue(report.is_file(), proc.stdout + proc.stderr)
        return proc, json.loads(report.read_text(encoding='utf-8'))

    def stdlib(self):
        return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                              cwd=self.root, capture_output=True, text=True, encoding='utf-8', timeout=30)

    def assert_accounted(self, data):
        self.assertEqual(data['tests_run'], len(data['executed_ids']))
        executed, omitted = data['executed_ids'], data['fixture_omitted_ids']
        self.assertEqual(len(executed), len(set(executed)))
        self.assertEqual(len(omitted), len(set(omitted)))
        self.assertFalse(set(executed) & set(omitted))
        self.assertEqual(sorted(executed + omitted), data['expected_ids'])

    def test_set_up_class_skip_does_not_count_unexecuted_cases(self):
        self.source('import unittest\nclass T(unittest.TestCase):\n'
                    ' @classmethod\n def setUpClass(cls): raise unittest.SkipTest("class prerequisite")\n'
                    ' def test_a(self): self.fail("unreachable")\n'
                    ' def test_b(self): self.fail("unreachable")\n')
        self.assertEqual(self.stdlib().returncode, 0)
        for workers in (1, 4):
            proc, data = self.execute(workers)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assert_accounted(data)
            self.assertEqual(data['tests_run'], 0)
            self.assertEqual(len(data['fixture_omitted_ids']), 2)
            self.assertEqual(len(data['fixture_outcomes']), 1)
            self.assertEqual(data['fixture_outcomes'][0]['reason'], 'class prerequisite')

    def test_set_up_module_skip_preserves_fixture_identity_and_reason(self):
        self.source('import unittest\ndef setUpModule(): raise unittest.SkipTest("module prerequisite")\n'
                    'class T(unittest.TestCase):\n def test_a(self): self.fail("unreachable")\n')
        self.assertEqual(self.stdlib().returncode, 0)
        for workers in (1, 4):
            proc, data = self.execute(workers)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assert_accounted(data)
            fixture = data['fixture_outcomes'][0]
            self.assertEqual((fixture['scope'], fixture['status'], fixture['reason']),
                             ('module', 'skipped', 'module prerequisite'))
            self.assertEqual(fixture['affected_ids'], data['expected_ids'])

    def test_import_skip_matches_stdlib_without_becoming_an_error(self):
        self.source('import unittest\nraise unittest.SkipTest("import prerequisite")\n')
        self.assertEqual(self.stdlib().returncode, 0)
        for workers in (1, 4):
            proc, data = self.execute(workers)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(data['ok'])
            self.assertEqual(data['errors'], [])
            self.assert_accounted(data)
            self.assertTrue(any(f['scope'] == 'import' and f['reason'] == 'import prerequisite'
                                for f in data['fixture_outcomes']))

    def test_class_skip_does_not_suppress_neighboring_class(self):
        self.source('import unittest\nfrom pathlib import Path\n'
                    '@unittest.skip("class decorator")\nclass A(unittest.TestCase):\n'
                    ' def test_a(self): self.fail("unreachable")\n'
                    'class B(unittest.TestCase):\n'
                    ' @classmethod\n def setUpClass(cls): raise unittest.SkipTest("fixture skip")\n'
                    ' def test_b(self): self.fail("unreachable")\n'
                    'class C(unittest.TestCase):\n'
                    ' def test_c(self): Path("neighbor").write_text("executed")\n')
        for workers in (1, 4):
            proc, data = self.execute(workers)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assert_accounted(data)
            self.assertEqual(data['tests_run'], 2)
            self.assertEqual(len(data['fixture_omitted_ids']), 1)
            self.assertEqual(len(data['skipped']), 1)
            self.assertEqual((self.root / 'neighbor').read_text(), 'executed')

    def test_fixture_errors_are_failures_and_never_skips(self):
        for hook in ('setUpModule', 'tearDownModule'):
            self.source('import unittest\ndef ' + hook + '(): raise RuntimeError("real fixture failure")\n'
                        'class T(unittest.TestCase):\n def test_a(self): self.assertEqual(2,2)\n')
            self.assertNotEqual(self.stdlib().returncode, 0)
            for workers in (1, 4):
                with self.subTest(hook=hook, workers=workers):
                    proc, data = self.execute(workers)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertFalse(data['ok'])
                    self.assert_accounted(data)
                    self.assertTrue(any(f['status'] == 'error' for f in data['fixture_outcomes']))
                    self.assertEqual(data['skipped'], [])

    def test_load_tests_function_cases_keep_order_and_execute_again(self):
        self.source('import unittest\nfrom pathlib import Path\n'
                    'def first():\n'
                    ' p=Path("order"); p.write_text((p.read_text() if p.exists() else "")+"a")\n'
                    'def second():\n'
                    ' p=Path("order"); assert p.read_text().endswith("a"); p.write_text(p.read_text()+"b")\n'
                    'def load_tests(loader, tests, pattern):\n'
                    ' return unittest.TestSuite([unittest.FunctionTestCase(first),unittest.FunctionTestCase(second)])\n')
        reference = self.stdlib()
        self.assertEqual(reference.returncode, 0, reference.stderr)
        (self.root / 'order').unlink()
        for workers in (1, 4, 4):
            proc, data = self.execute(workers)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assert_accounted(data)
            self.assertEqual(data['tests_run'], 2)
            self.assertEqual(data['expected_ids'], ['first', 'second'])
        self.assertEqual((self.root / 'order').read_text(), 'ababab')

    def test_package_load_tests_keeps_its_suite_and_hooks(self):
        package = self.tests / 'pkg'
        package.mkdir()
        (package / '__init__.py').write_text(
            'import unittest\nfrom pathlib import Path\n'
            'def check_package(): Path("package-ran").write_text("ok")\n'
            'def load_tests(loader, tests, pattern):\n'
            ' return unittest.TestSuite([unittest.FunctionTestCase(check_package)])\n', encoding='utf-8')
        self.assertEqual(self.stdlib().returncode, 0)
        (self.root / 'package-ran').unlink()
        proc, data = self.execute(4)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assert_accounted(data)
        self.assertEqual(data['expected_ids'], ['check_package'])
        self.assertEqual((self.root / 'package-ran').read_text(), 'ok')

    def test_import_error_and_discovery_abort_cannot_become_skips(self):
        for source in ('raise RuntimeError("broken import")\n', 'import os\nos._exit(0)\n'):
            self.source(source)
            for workers in (1, 4):
                proc, data = self.execute(workers)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(data['ok'])
                self.assertTrue(data['errors'])

    def test_unbacked_or_foreign_fixture_omissions_are_rejected(self):
        self.source('import unittest\nclass T(unittest.TestCase):\n'
                    ' @classmethod\n def setUpClass(cls): raise unittest.SkipTest("fixture skip")\n'
                    ' def test_a(self): self.fail("unreachable")\n')
        proc, data = self.execute(1)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assert_accounted(data)
        spec = importlib.util.spec_from_file_location('kdd_fixture_report_validator', RUNNER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.validate_report(data['expected_ids'], data), [])
        variants = []
        unbacked = copy.deepcopy(data); unbacked['fixture_outcomes'] = []; variants.append(unbacked)
        foreign = copy.deepcopy(data); foreign['fixture_omitted_ids'] = ['foreign.test']; variants.append(foreign)
        forged = copy.deepcopy(data); forged['executed_ids'] = data['expected_ids']; variants.append(forged)
        missing = copy.deepcopy(data); missing['fixture_omitted_ids'] = []; variants.append(missing)
        for variant in variants:
            self.assertTrue(module.validate_report(data['expected_ids'], variant), variant)


if __name__ == '__main__':
    unittest.main()
