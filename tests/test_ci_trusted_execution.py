"""Real Git and interpreter oracle for the trusted startup boundary."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = ('trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
         'validate_contracts.py', 'process_tree.py', 'execution_profile.py')


class TrustedExecution(unittest.TestCase):
    def setUp(self):
        case = tempfile.TemporaryDirectory(prefix='kdd trusted \u00f1 ')
        self.addCleanup(case.cleanup)
        self.outer = Path(case.name)
        self.repo = self.outer / 'candidate with spaces'
        (self.repo / 'scripts').mkdir(parents=True)
        (self.repo / 'tests').mkdir()
        (self.repo / 'knowledge/contracts').mkdir(parents=True)
        self.env = dict(os.environ, PYTHONUTF8='1', GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL=os.devnull)
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'PYTHONPATH'):
            self.env.pop(key, None)
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + self.env.get('PATH', '')
        for name in FILES:
            source = ROOT / 'scripts' / name
            if source.is_file():
                shutil.copy2(source, self.repo / 'scripts' / name)
        (self.repo / 'feature.py').write_text('value = 42\n', encoding='utf-8')
        (self.repo / 'tests/test_feature.py').write_text(
            'import unittest\nfrom pathlib import Path\nfrom feature import value\n'
            'class Feature(unittest.TestCase):\n'
            ' def test_value(self):\n'
            '  p=Path("runs"); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n'
            '  self.assertEqual(value,42)\n', encoding='utf-8')
        # A frozen contract that invokes the KDD runner itself, as in the audit.
        oracle = self.repo / 'tests/test_feature.py'
        seal = hashlib.sha256(oracle.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        (self.repo / 'knowledge/contracts/feature.md').write_text(
            "---\ntype: 'Task Contract'\ntitle: 'Fixture'\ndescription: 'Real oracle'\n"
            "tags: ['testing']\ntask: fixture\nintent: 'Check feature'\n"
            "signature: 'value = 42'\nbudget:\n  cyclomatic_max: 4\n"
            "touch_only: ['feature.py']\ndeps_allowed: ['stdlib']\nforbids: ['network']\n"
            "tests: tests/test_feature.py\ntests_sha256: '" + seal + "'\n"
            "test_command: 'python scripts/run_test_suite.py --start-directory tests'\n"
            "target: feature.py\n---\n## Intent\nCheck feature.\n## Interface\nvalue.\n"
            "## Invariants\n42.\n## Examples\n- correct\n- incorrect\n"
            "## Do / Don't\nKeep assertions.\n## Tests\nReal oracle.\n"
            "## Constraints\nPARAR y reportar si no hay oracle.\n", encoding='utf-8')
        self.git('init', '-q', '-b', 'main')
        for key, value in [('user.name', 'Fixture reviewer'), ('user.email', 'reviewer@example.invalid'),
                           ('core.autocrlf', 'false'), ('commit.gpgsign', 'false'),
                           ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
            self.git('config', key, value)
        self.base = self.commit('Reviewed runtime and oracle')

    def run_command(self, argv, env=None):
        return subprocess.run(argv, cwd=self.repo, env=env or self.env,
                              capture_output=True, text=True, encoding='utf-8', timeout=45)

    def git(self, *args):
        proc = self.run_command(['git', *args])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def guard(self, candidate):
        # Use the original trusted guard, never the one from the candidate.
        code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
                'from guard_pr_baseline import check;'
                'print(json.dumps(check(*sys.argv[2:])))')
        proc = self.run_command([sys.executable, '-I', '-c', code, str(ROOT / 'scripts'),
                                 self.base, candidate, self.base])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def bundle(self):
        entry = ROOT / 'scripts/trusted_ci.py'
        self.assertTrue(entry.is_file(), 'Missing contracted trusted launcher')
        bundle = self.outer / 'approved runtime'
        proc = self.run_command([sys.executable, '-I', str(entry), 'prepare',
                                 '--repo-root', str(self.repo), '--trusted-ref', self.base,
                                 '--bundle-dir', str(bundle)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for name in FILES:
            expected = subprocess.check_output(['git', 'show', self.base + ':scripts/' + name],
                                               cwd=self.repo, env=self.env)
            self.assertEqual((bundle / name).read_bytes(), expected)
        return bundle

    def execute(self, bundle, mode='suite', report=None, env=None):
        argv = [sys.executable, '-I', str(bundle / 'trusted_ci.py'), mode,
                '--repo-root', str(self.repo), '--workers', '4']
        argv += (['--start-directory', 'tests'] if mode == 'suite' else
                 ['--contracts-dir', 'knowledge/contracts', '--timeout', '20', '--deduplicate'])
        argv += ['--report-json', str(report or self.outer / 'result.json')]
        return self.run_command(argv, env=env)

    def test_guard_rejects_stdlib_shadow_without_executing_it(self):
        for path in ('scripts/argparse.py', 'json.py', 'scripts/subprocess/__init__.py'):
            with self.subTest(path=path):
                target = self.repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('from pathlib import Path\nPath("executed-shadow").touch()\n', encoding='utf-8')
                candidate = self.commit('Attempt a shadow import')
                self.assertTrue(self.guard(candidate), path)
                self.assertFalse((self.repo / 'executed-shadow').exists())
                target.unlink()

    def test_guard_protects_new_runtime_helpers(self):
        for name in ('trusted_ci.py', 'process_tree.py', 'execution_profile.py'):
            with self.subTest(name=name):
                (self.repo / 'scripts' / name).write_text('raise SystemExit(0)\n', encoding='utf-8')
                candidate = self.commit('Attempt to replace trusted helper')
                findings = self.guard(candidate)
                self.assertTrue(any('scripts/' + name in finding for finding in findings), findings)

    def test_guard_allows_an_ordinary_implementation_module(self):
        (self.repo / 'scripts/ordinary_feature.py').write_text('answer = 42\n', encoding='utf-8')
        candidate = self.commit('Legitimate implementation')
        self.assertEqual(self.guard(candidate), [])

    def test_bundle_and_two_real_passes_are_independent(self):
        bundle = self.bundle()
        for number in (1, 2):
            report = self.outer / ('pass-' + str(number) + '.json')
            proc = self.execute(bundle, report=report)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(data['ok'])
            self.assertEqual(data['tests_run'], 1)
            self.assertEqual(data['executed_ids'], ['test_feature.Feature.test_value'])
            self.assertEqual((self.repo / 'runs').read_text(), str(number))

    def test_shadow_cannot_hide_a_real_failure_in_suite_or_contract_commands(self):
        bundle = self.bundle()
        (self.repo / 'feature.py').write_text('value = 0\n', encoding='utf-8')
        (self.repo / 'scripts/argparse.py').write_text('raise SystemExit(0)\n', encoding='utf-8')
        for mode in ('suite', 'commands'):
            with self.subTest(mode=mode):
                (self.repo / 'runs').unlink(missing_ok=True)
                report = self.outer / (mode + '.json')
                proc = self.execute(bundle, mode=mode, report=report)
                self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertTrue(report.is_file(), proc.stdout + proc.stderr)
                self.assertFalse(json.loads(report.read_text(encoding='utf-8'))['ok'])
                self.assertTrue((self.repo / 'runs').is_file(), 'The real oracle must have executed')

    def test_healthy_contract_command_executes_and_produces_structured_results(self):
        bundle = self.bundle()
        proc = self.execute(bundle, mode='commands')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads((self.outer / 'result.json').read_text())
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['results']), 1)
        self.assertTrue(data['results'][0]['ok'])
        self.assertEqual((self.repo / 'runs').read_text(), '1')

    def test_local_runner_startup_ignores_script_directory_stdlib_shadow(self):
        (self.repo / 'scripts/argparse.py').write_text('raise SystemExit(0)\n', encoding='utf-8')
        report = self.outer / 'local-runner.json'
        proc = self.run_command([sys.executable, 'scripts/run_test_suite.py',
                                 '--start-directory', 'tests', '--workers', '1',
                                 '--report-json', str(report)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(report.is_file(), 'Exit 0 without report is not successful execution')
        self.assertEqual(json.loads(report.read_text())['tests_run'], 1)
        self.assertEqual((self.repo / 'runs').read_text(), '1')

    def test_candidate_runner_replacement_does_not_replace_external_bundle(self):
        bundle = self.bundle()
        (self.repo / 'scripts/run_test_suite.py').write_text('raise SystemExit(0)\n', encoding='utf-8')
        (self.repo / 'feature.py').write_text('value = 0\n', encoding='utf-8')
        proc = self.execute(bundle)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('test_feature.Feature.test_value', (self.outer / 'result.json').read_text())

    def test_pythonpath_and_sitecustomize_do_not_run_before_control(self):
        bundle = self.bundle()
        poisoned = self.outer / 'poisoned'
        poisoned.mkdir()
        marker = self.outer / 'startup-ran'
        payload = 'from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\nraise SystemExit(0)\n'
        for name in ('sitecustomize.py', 'argparse.py'):
            (poisoned / name).write_text(payload, encoding='utf-8')
        proc = self.execute(bundle, env=dict(self.env, PYTHONPATH=str(poisoned)))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual((self.repo / 'runs').read_text(), '1')

    def test_oracle_exit_zero_without_report_is_failure(self):
        bundle = self.bundle()
        (self.repo / 'tests/test_feature.py').write_text(
            'import unittest,os\nclass T(unittest.TestCase):\n'
            ' def test_exit(self): os._exit(0)\n', encoding='utf-8')
        proc = self.execute(bundle)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(json.loads((self.outer / 'result.json').read_text())['ok'])

    def test_reused_report_is_rejected_before_tests(self):
        bundle = self.bundle()
        report = self.outer / 'old.json'
        report.write_text('{"ok":true}', encoding='utf-8')
        proc = self.execute(bundle, report=report)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(report.read_text(), '{"ok":true}')
        self.assertFalse((self.repo / 'runs').exists())

    def test_prepare_rejects_head_invalid_ref_missing_files_and_internal_destination(self):
        entry = ROOT / 'scripts/trusted_ci.py'
        self.assertTrue(entry.is_file(), 'Missing contracted trusted launcher')
        for ref, destination in [('HEAD', self.outer / 'head'), ('f' * 40, self.outer / 'missing'),
                                  (self.base, self.repo / 'unsafe-bundle')]:
            with self.subTest(ref=ref, destination=destination):
                proc = self.run_command([sys.executable, '-I', str(entry), 'prepare',
                                         '--repo-root', str(self.repo), '--trusted-ref', ref,
                                         '--bundle-dir', str(destination)])
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(destination.exists())
        (self.repo / 'scripts/run_test_suite.py').unlink()
        incomplete = self.commit('Incomplete runtime')
        destination = self.outer / 'incomplete'
        proc = self.run_command([sys.executable, '-I', str(entry), 'prepare',
                                 '--repo-root', str(self.repo), '--trusted-ref', incomplete,
                                 '--bundle-dir', str(destination)])
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(destination.exists())

    def test_report_directory_allocates_new_evidence_for_identical_commands(self):
        bundle = self.bundle()
        directory = self.outer / 'reports'
        argv = [sys.executable, '-I', str(bundle / 'trusted_ci.py'), 'suite',
                '--repo-root', str(self.repo), '--start-directory', 'tests',
                '--workers', '1', '--report-dir', str(directory)]
        for _ in range(2):
            proc = self.run_command(argv)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        reports = list(directory.glob('*.json'))
        self.assertEqual(len(reports), 2)
        self.assertTrue(all(json.loads(p.read_text())['tests_run'] == 1 for p in reports))
        self.assertEqual((self.repo / 'runs').read_text(), '2')


if __name__ == '__main__':
    unittest.main()
