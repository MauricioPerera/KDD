"""Independent integration oracle: complete inventories and real processes."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/run_test_suite.py'
COMMAND = 'run: python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . --start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" --report-dir "$RUNNER_TEMP/kdd-suite-reports"'


class SuiteProcesses(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='kdd suite oracle ')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.tests = self.root / 'tests'
        self.tests.mkdir()
        self.prefix = 'test_fixture_' + uuid.uuid4().hex + '_'

    def module(self, suffix, source):
        path = self.tests / (self.prefix + suffix + '.py')
        path.write_text(source, encoding='utf-8')
        return path.stem

    def passing(self, suffix='a'):
        return self.module(suffix, 'import unittest\nclass T(unittest.TestCase):\n'
                           '    def test_ok(self): self.assertEqual(2+2,4)\n')

    def execute(self, workers=1):
        self.assertTrue(RUNNER.is_file(), 'Missing contracted suite runner')
        report = self.root / ('report-' + uuid.uuid4().hex + '.json')
        proc = subprocess.run(
            [sys.executable, str(RUNNER), '--start-directory', str(self.tests),
             '--pattern', 'test_*.py', '--workers', str(workers),
             '--report-json', str(report)], cwd=self.root,
            capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertTrue(report.is_file(), proc.stdout + proc.stderr)
        data = json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(data['version'], 1)
        return proc, data

    def inventory(self):
        # An independent standard-library discovery, outside the candidate runner.
        source = (
            'import json,unittest\n'
            'def walk(s):\n'
            ' for t in s:\n'
            '  if isinstance(t,unittest.TestSuite): yield from walk(t)\n'
            '  else: yield t.id()\n'
            's=unittest.TestLoader().discover(' + repr(str(self.tests)) +
            ',pattern="test_*.py")\nprint(json.dumps(sorted(walk(s))))\n')
        proc = subprocess.run([sys.executable, '-c', source], cwd=self.root,
                              capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def assert_complete(self, proc, report, ids):
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(report['ok'])
        self.assertEqual(report['expected_ids'], ids)
        self.assertEqual(report['executed_ids'], ids)
        self.assertEqual(report['tests_run'], len(ids))
        self.assertEqual(report['failures'], [])
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['unexpected_successes'], [])

    def test_serial_and_parallel_match_unittest_with_skips_and_expected_failure(self):
        self.module('a', 'import unittest\nclass T(unittest.TestCase):\n'
                    ' def test_ok(self): self.assertTrue(True)\n'
                    ' @unittest.skip("fixture reason")\n'
                    ' def test_skip(self): self.fail("must stay skipped")\n'
                    ' @unittest.expectedFailure\n'
                    ' def test_xfail(self): self.assertEqual(1,2)\n')
        self.passing('b')
        ids = self.inventory()
        self.assertEqual(len(ids), 4)
        for workers in (1, 2):
            with self.subTest(workers=workers):
                proc, report = self.execute(workers)
                self.assert_complete(proc, report, ids)
                self.assertEqual(len(report['skipped']), 1)
                self.assertEqual(report['skipped'][0]['reason'], 'fixture reason')
                self.assertEqual(len(report['expected_failures']), 1)

    def test_module_and_class_fixtures_are_not_split_between_workers(self):
        self.module('a', '''import unittest
from pathlib import Path
def bump(name):
 p=Path(name); p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
def setUpModule(): bump('module.setup')
def tearDownModule(): bump('module.teardown')
class T(unittest.TestCase):
 @classmethod
 def setUpClass(cls): bump('class.setup')
 @classmethod
 def tearDownClass(cls): bump('class.teardown')
 def test_a(self): self.assertEqual(Path('class.setup').read_text(),'1')
 def test_b(self): self.assertEqual(Path('module.setup').read_text(),'1')
''')
        proc, report = self.execute(2)
        self.assert_complete(proc, report, self.inventory())
        for name in ('module.setup', 'module.teardown', 'class.setup', 'class.teardown'):
            self.assertEqual((self.root / name).read_text(), '1', name)

    def test_recursive_package_discovery_retains_all_ids(self):
        self.passing()
        package = self.tests / ('pkg_' + uuid.uuid4().hex)
        package.mkdir()
        (package / '__init__.py').write_text('', encoding='utf-8')
        (package / 'test_nested.py').write_text(
            'import unittest\nclass T(unittest.TestCase):\n'
            ' def test_nested(self): self.assertEqual(5,5)\n', encoding='utf-8')
        ids = self.inventory()
        self.assertEqual(len(ids), 2)
        for workers in (1, 2):
            proc, report = self.execute(workers)
            self.assert_complete(proc, report, ids)

    def test_real_process_barrier_and_observed_concurrency_bound(self):
        for number in range(4):
            self.module(str(number), '''import json,os,time,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_work(self):
  start=time.monotonic_ns(); number=NUMBER
  Path(str(number)+'.ready').write_text(str(os.getpid()))
  try:
   if number<2:
    deadline=time.monotonic()+5
    while not Path(str(1-number)+'.ready').exists() and time.monotonic()<deadline:
     time.sleep(.01)
    self.assertTrue(Path(str(1-number)+'.ready').exists(),'no concurrent peer')
   time.sleep(.15)
  finally:
   Path(str(number)+'.event').write_text(json.dumps([start,time.monotonic_ns(),os.getpid()]))
'''.replace('NUMBER', str(number)))
        proc, report = self.execute(2)
        self.assert_complete(proc, report, self.inventory())
        events = [json.loads(p.read_text()) for p in self.root.glob('*.event')]
        self.assertEqual(len(events), 4)
        self.assertGreaterEqual(len({e[2] for e in events}), 2)
        transitions = sorted([(start, 1) for start, end, pid in events] +
                             [(end, -1) for start, end, pid in events])
        active = peak = 0
        for stamp, delta in transitions:
            active += delta
            peak = max(peak, active)
        self.assertEqual(peak, 2, 'actual overlap must equal the requested bound')

    def test_processes_isolate_cwd_and_environment_and_keep_original_cwd(self):
        self.module('a', '''import os,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_change(self):
  os.environ['KDD_FIXTURE_LEAK']='bad'
  Path('elsewhere').mkdir(); os.chdir('elsewhere')
  self.assertEqual(Path.cwd().name,'elsewhere')
''')
        self.module('b', '''import os,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_clean(self):
  self.assertNotIn('KDD_FIXTURE_LEAK',os.environ)
  self.assertTrue(Path('tests').is_dir())
''')
        proc, report = self.execute(2)
        self.assert_complete(proc, report, self.inventory())

    def test_second_invocation_executes_again_with_same_inventory(self):
        self.module('a', '''import unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_count(self):
  p=Path('count'); p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
  self.assertTrue(p.is_file())
''')
        ids = self.inventory()
        for expected in (1, 2):
            proc, report = self.execute(2)
            self.assert_complete(proc, report, ids)
            self.assertEqual((self.root / 'count').read_text(), str(expected))

    def test_failure_is_not_hidden_and_other_modules_still_execute(self):
        self.module('a', 'import unittest\nclass T(unittest.TestCase):\n'
                    ' def test_bad(self): self.assertEqual(1,2)\n')
        self.passing('b')
        proc, report = self.execute(2)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(report['ok'])
        self.assertEqual(report['executed_ids'], self.inventory())
        self.assertEqual(report['tests_run'], 2)
        self.assertEqual(len(report['failures']), 1)

    def test_unexpected_success_is_a_failure(self):
        self.module('a', 'import unittest\nclass T(unittest.TestCase):\n'
                    ' @unittest.expectedFailure\n'
                    ' def test_bad_expectation(self): self.assertTrue(True)\n')
        proc, report = self.execute(2)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(report['ok'])
        self.assertEqual(len(report['unexpected_successes']), 1)

    def test_discovery_error_cannot_become_an_empty_success(self):
        self.module('broken', 'raise RuntimeError("fixture import error")\n')
        proc, report = self.execute(2)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(report['ok'])
        self.assertTrue(report['errors'])

    def test_worker_exit_zero_without_report_is_failure(self):
        self.module('a', 'import os,unittest\nclass T(unittest.TestCase):\n'
                    ' def test_exit(self): os._exit(0)\n')
        proc, report = self.execute(2)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(report['ok'])
        self.assertTrue(report['errors'])

    def test_empty_suite_fails(self):
        proc, report = self.execute(2)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(report['ok'])
        self.assertEqual(report['tests_run'], 0)

    def test_duplicate_discovery_ids_fail_before_executing(self):
        self.module('a', '''import unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_once(self): Path('unexpected').write_text('executed')
def load_tests(loader,tests,pattern):
 return unittest.TestSuite([T('test_once'),T('test_once')])
''')
        proc, report = self.execute(2)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(report['ok'])
        self.assertFalse((self.root / 'unexpected').exists())

    def test_invalid_workers_never_execute_fixture(self):
        self.module('a', 'import unittest\nfrom pathlib import Path\n'
                    'class T(unittest.TestCase):\n'
                    ' def test_work(self): Path("unexpected").touch()\n')
        self.assertTrue(RUNNER.is_file(), 'Missing contracted suite runner')
        for value in ('0', '-1', '9', '1.5', 'abc', '$(echo bad)'):
            with self.subTest(value=value):
                result = subprocess.run([sys.executable, str(RUNNER),
                                         '--start-directory', str(self.tests),
                                         '--workers', value], cwd=self.root,
                                        capture_output=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / 'unexpected').exists())

    def test_paths_with_unicode_and_decorative_failure_output(self):
        renamed = self.root / 'pruebas con espacio \u00f1'
        self.tests.rename(renamed)
        self.tests = renamed
        self.module('a', 'import unittest\nclass T(unittest.TestCase):\n'
                    ' def test_ok(self):\n'
                    '  print("FAIL ERROR fixture only")\n'
                    '  self.assertEqual(3,3)\n')
        proc, report = self.execute(2)
        self.assert_complete(proc, report, self.inventory())

    def test_report_validator_rejects_missing_duplicate_and_falsified_outcomes(self):
        self.passing()
        proc, report = self.execute(1)
        ids = self.inventory()
        self.assert_complete(proc, report, ids)
        spec = importlib.util.spec_from_file_location('kdd_suite_oracle_candidate', RUNNER)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(module)
        self.assertEqual(module.validate_report(ids, report), [])
        variants = [dict(report, executed_ids=[]),
                    dict(report, executed_ids=ids + ids),
                    dict(report, executed_ids=['foreign.T.test_nope']),
                    dict(report, tests_run=99),
                    dict(report, failures=[{'id': ids[0], 'traceback': 'actual failure'}]),
                    dict(report, skipped=[{'id': 'foreign.T.test_nope', 'reason': 'fake'}]),
                    dict(report, errors='malformed'),
                    {'version': 1, 'ok': True}]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertTrue(module.validate_report(ids, copy.deepcopy(variant)))

    def test_new_suite_runner_is_protected_by_the_trusted_base_guard(self):
        def git(*args):
            proc = subprocess.run(['git', *args], cwd=self.root, capture_output=True,
                                  text=True, encoding='utf-8', timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout.strip()
        git('init', '-q', '--initial-branch=main')
        git('config', 'user.name', 'Fixture reviewer')
        git('config', 'user.email', 'reviewer@example.test')
        contracts = self.root / 'knowledge/contracts'
        contracts.mkdir(parents=True)
        (contracts / 'fixture.md').write_text('---\ntests: tests/protected.py\n---\n', encoding='utf-8')
        (self.tests / 'protected.py').write_text('assert 1 == 1\n', encoding='utf-8')
        candidate = self.root / 'scripts/run_test_suite.py'
        candidate.parent.mkdir()
        candidate.write_text('print("original runner")\n', encoding='utf-8')
        git('add', '.')
        git('commit', '-qm', 'Reviewed fixture baseline')
        base = git('rev-parse', 'HEAD')
        candidate.write_text('from pathlib import Path\nPath("forged").touch()\n', encoding='utf-8')
        git('add', '.')
        git('commit', '-qm', 'Attempt to replace suite runner')
        head = git('rev-parse', 'HEAD')
        source = ('import json,sys\nsys.path.insert(0,' + repr(str(ROOT / 'scripts')) + ')\n'
                  'from guard_pr_baseline import check\nprint(json.dumps(check(' +
                  repr(base) + ',' + repr(head) + ',' + repr(base) + ')))\n')
        proc = subprocess.run([sys.executable, '-c', source], cwd=self.root,
                              capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('scripts/run_test_suite.py: trusted gate file changed in PR',
                      json.loads(proc.stdout))
        self.assertFalse((self.root / 'forged').exists())


class WorkflowIntegration(unittest.TestCase):
    def test_full_dual_os_suite_two_identical_passes_and_safe_consumer_defaults(self):
        text = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertEqual(text.count('os: [ubuntu-latest, windows-latest]'), 2)
        self.assertEqual(text.count(COMMAND), 2)
        for number in (1, 2):
            step = text.split('- name: Run unit tests (%s/2)' % number)[1].split('\n      - ')[0]
            self.assertIn(COMMAND, step)
            self.assertIn("KDD_SKIP_INIT_POST_APPLY_SUITE: '1'", step)
        for name in ('suite_workers', 'contract_workers'):
            self.assertIn(name + ":\n        type: string\n        default: '1'", text)
            self.assertIn("inputs." + name + " || (!inputs.reusable_execution && github.repository == 'MauricioPerera/KDD' && '4' || '1')", text)
        self.assertIn('--timeout 600 --deduplicate --workers "$KDD_CONTRACT_WORKERS"', text)
        self.assertIn('Check approved contract and oracle baseline', text)
        self.assertIn('Validate Git task snapshots and transitions', text)
        self.assertIn('run: npm test', text)
        self.assertNotIn('continue-on-error:', text)


if __name__ == '__main__':
    unittest.main()
