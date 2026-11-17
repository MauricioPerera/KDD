"""Oracle for a diagnostic projection of real, pinned CI runtime reports."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/ci_timings.py'
SENTINEL = 'PRIVATE_OUTPUT_MUST_NOT_BE_PUBLISHED'


class TimingDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area = tempfile.TemporaryDirectory(prefix='kdd timing fixture ')
        cls.addClassCleanup(cls.area.cleanup)
        base = Path(cls.area.name)
        cls.project = base / 'project'
        tests = cls.project / 'tests'
        tests.mkdir(parents=True)
        (tests / '__init__.py').write_text('', encoding='utf-8')
        (tests / 'test_product.py').write_text(
            'import unittest\nclass Product(unittest.TestCase):\n'
            ' def test_real(self):\n  self.assertEqual(2 + 2, 4)\n', encoding='utf-8')
        cls.bundle = base / 'bundle'
        seed = base / 'runtime-source'
        (seed / 'scripts').mkdir(parents=True)
        # A real Git fixture also works after init_project removes upstream history.
        files = ('trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
                 'validate_contracts.py', 'process_tree.py', 'execution_profile.py',
                 'oracle_execution.py', 'oracle_inventory.py',
                 'unittest_oracle_runner.py', 'node_oracle_reporter.mjs')
        for name in files:
            (seed / 'scripts' / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
        cls.checked(['git', '-C', str(seed), 'init', '-q'])
        configure_git(seed, {'user.name': 'Timing Fixture', 'user.email': 'timing@example.invalid',
                            'core.autocrlf': 'false', 'commit.gpgsign': 'false'}, ephemeral=True)
        cls.checked(['git', '-C', str(seed), 'add', 'scripts'])
        cls.checked(['git', '-C', str(seed), 'commit', '-qm', 'runtime fixture'])
        cls.pin = cls.checked(['git', '-C', str(seed), 'rev-parse', 'HEAD']).stdout.strip()
        cls.checked([sys.executable, '-I', str(ROOT / 'scripts/trusted_ci.py'),
                     'prepare', '--repo-root', str(seed), '--trusted-ref', cls.pin,
                     '--bundle-dir', str(cls.bundle)])
        reports = []
        for index in range(2):
            destination = base / ('pass-' + str(index) + '.json')
            cls.checked([sys.executable, '-I', str(cls.bundle / 'trusted_ci.py'),
                         'suite', '--repo-root', str(cls.project), '--workers', '2',
                         '--report-json', str(destination)])
            reports.append(json.loads(destination.read_text(encoding='utf-8')))
        cls.suites = reports
        contracts = cls.project / 'knowledge/contracts'
        contracts.mkdir(parents=True)
        seal = hashlib.sha256((tests / 'test_product.py').read_bytes()).hexdigest()
        (cls.project / 'product.py').write_text('VALUE = 4\n', encoding='utf-8')
        text = """---
type: 'Task Contract'
title: 'Timing fixture'
description: 'Execute a real oracle for diagnostic projection.'
tags: ['test']
task: fixture
intent: 'Execute a real oracle.'
target: product.py
signature: 'VALUE = 4'
test_command: 'python -m unittest tests/test_product.py'
test_runner: python-unittest
tests: tests/test_product.py
tests_sha256: 'SEAL'
oracle_files: ['tests/test_product.py', 'tests/__init__.py']
touch_only: ['product.py']
budget:
  cyclomatic_max: 3
deps_allowed: ['stdlib']
forbids: ['network']
---
## Intent
Exercise the diagnostic with a real process.
""".replace('SEAL', seal)
        (contracts / 'fixture.md').write_text(text, encoding='utf-8')
        destination = base / 'commands.json'
        cls.checked([sys.executable, '-I', str(cls.bundle / 'trusted_ci.py'),
                     'commands', '--repo-root', str(cls.project), '--contracts-dir', str(contracts),
                     '--workers', '1', '--report-json', str(destination)])
        cls.commands = json.loads(destination.read_text(encoding='utf-8'))

    @staticmethod
    def checked(argv):
        proc = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', timeout=60)
        if proc.returncode:
            raise AssertionError('Fixture process failed: ' + proc.stdout + proc.stderr)
        return proc

    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd timing input ')
        self.addCleanup(self.area.cleanup)
        self.base = Path(self.area.name)
        self.command_dir, self.suite_dir = self.base / 'commands', self.base / 'suites'
        self.command_dir.mkdir(); self.suite_dir.mkdir()
        self.output = self.base / 'timings.json'
        self.command = copy.deepcopy(self.commands)
        self.passes = copy.deepcopy(self.suites)

    def write_inputs(self):
        data = [(self.command_dir / 'evidence-command.json', self.command)]
        data += [(self.suite_dir / ('evidence-' + str(i) + '.json'), item)
                 for i, item in enumerate(self.passes)]
        for path, document in data:
            path.write_text(json.dumps(document), encoding='utf-8')

    def export(self, *, write=True, extra=()):
        self.assertTrue(SCRIPT.is_file(), 'Implementation intentionally absent until baseline approval')
        if write:
            self.write_inputs()
        return subprocess.run([sys.executable, '-I', str(SCRIPT), 'export',
            '--repo-root', str(self.project), '--commands-dir', str(self.command_dir),
            '--suites-dir', str(self.suite_dir), '--output', str(self.output),
            '--run-id', '123', '--run-attempt', '2', '--head-sha', 'a' * 40,
            '--platform', 'windows-latest' if sys.platform == 'win32' else 'ubuntu-latest',
            '--trusted-runtime-ref', self.pin, *extra],
            capture_output=True, text=True, encoding='utf-8', timeout=20)

    def document(self):
        result = self.export()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(self.output.read_text(encoding='utf-8'))

    def rejected(self):
        result = self.export()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(self.output.exists())
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_real_pinned_reports_produce_exact_metrics_and_source_hashes(self):
        report = self.document()
        self.assertEqual(set(report), {'schema_version', 'kind', 'identity', 'complete', 'missing', 'sources'})
        self.assertEqual(report['kind'], 'kdd-ci-timings')
        self.assertEqual(report['schema_version'], 1)
        self.assertTrue(report['complete'])
        self.assertEqual(report['missing'], [])
        self.assertEqual(report['identity'], {'run_id': 123, 'run_attempt': 2,
            'head_sha': 'a' * 40, 'platform': 'windows-latest' if sys.platform == 'win32' else 'ubuntu-latest',
            'trusted_runtime_ref': self.pin})
        sources = report['sources']
        self.assertEqual(len(sources), 3)
        for source in sources:
            self.assertEqual(set(source), {'kind', 'source_sha256', 'recorded_ok', 'duration_seconds', 'rows'})
            self.assertTrue(source['recorded_ok'])
        actual = {s['source_sha256'] for s in sources}
        expected = {hashlib.sha256(p.read_bytes()).hexdigest()
                    for folder in (self.command_dir, self.suite_dir) for p in folder.glob('evidence-*.json')}
        self.assertEqual(actual, expected)
        suites = [s for s in sources if s['kind'] == 'suite']
        self.assertEqual(sorted(s['duration_seconds'] for s in suites),
                         sorted(s['duration_seconds'] for s in self.passes))
        for source in suites:
            self.assertEqual(len(source['rows']), 1)
            row = source['rows'][0]
            self.assertEqual(set(row), {'module', 'duration_seconds', 'tests_run', 'exit_code'})
            self.assertEqual(row['module'], 'test_product')
            self.assertEqual(row['tests_run'], 1)
            self.assertEqual(row['exit_code'], 0)
            original = next(s for s in self.passes if s['duration_seconds'] == source['duration_seconds'])
            self.assertEqual(row['duration_seconds'], original['modules'][0]['duration_seconds'])
        command = next(s for s in sources if s['kind'] == 'commands')
        self.assertIsNone(command['duration_seconds'], 'A sum of concurrent commands is not elapsed wall time')
        self.assertEqual(command['rows'][0], {'contract': 'knowledge/contracts/fixture.md',
            'scope': 'product', 'duration_seconds': self.command['results'][0]['duration_seconds'],
            'exit_code': 0, 'recorded_ok': True, 'shared_from': None})

    def test_arbitrary_outputs_errors_commands_and_extra_fields_are_never_published(self):
        for item in [self.command, *self.passes, *self.command['results'],
                     *(m for s in self.passes for m in s['modules'])]:
            item.update(stdout=SENTINEL, stderr=SENTINEL, error=SENTINEL,
                        test_command=SENTINEL, environment={'PRIVATE': SENTINEL})
        report = self.document()
        self.assertNotIn(SENTINEL, json.dumps(report))

    def test_failure_exit_and_timeout_are_diagnostics_never_success_claims(self):
        self.command['ok'] = False
        self.command['results'][0].update(ok=False, exit_code=None, error='timeout')
        self.passes[0]['ok'] = False
        self.passes[0]['modules'][0]['exit_code'] = 1
        report = self.document()
        command = next(s for s in report['sources'] if s['kind'] == 'commands')
        self.assertFalse(command['recorded_ok'])
        self.assertIsNone(command['rows'][0]['exit_code'])
        self.assertFalse(command['rows'][0]['recorded_ok'])
        self.assertIn(False, [s['recorded_ok'] for s in report['sources'] if s['kind'] == 'suite'])

    def test_shared_commands_have_zero_duration_and_keep_representative(self):
        shared = copy.deepcopy(self.command['results'][0])
        shared.update(path=str(self.project / 'knowledge/contracts/shared.md'),
                      shared_from=self.command['results'][0]['path'], duration_seconds=0)
        self.command['results'].append(shared)
        self.command['contracts'] = 2
        report = self.document()
        row = next(s for s in report['sources'] if s['kind'] == 'commands')['rows'][1]
        self.assertEqual(row['duration_seconds'], 0)
        self.assertEqual(row['shared_from'], 'knowledge/contracts/fixture.md')

    def test_missing_reports_are_explicit_incomplete_diagnostics(self):
        self.write_inputs()
        (self.suite_dir / 'evidence-1.json').unlink()
        result = self.export(write=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertFalse(report['complete'])
        self.assertEqual(report['missing'], ['suite-report-2'])

    def test_duplicate_reports_are_rejected_instead_of_counted_as_two_passes(self):
        self.passes[1] = copy.deepcopy(self.passes[0])
        self.rejected()

    def test_runtime_mismatch_is_rejected(self):
        self.passes[0]['trusted_runtime_ref'] = 'b' * 40
        self.rejected()

    def test_nonfinite_negative_boolean_and_missing_durations_are_rejected(self):
        original = copy.deepcopy(self.passes)
        for value in (float('nan'), float('inf'), -1, True, None):
            with self.subTest(value=value):
                self.passes = copy.deepcopy(original)
                self.passes[0]['modules'][0]['duration_seconds'] = value
                self.rejected()

    def test_paths_outside_checkout_and_unsafe_module_labels_are_rejected(self):
        original = copy.deepcopy(self.command)
        self.command['results'][0]['path'] = str(self.base / 'outside.md')
        self.rejected()
        self.command = original
        self.passes[0]['modules'][0]['module'] = '<script>' + SENTINEL
        self.rejected()

    def test_malformed_and_excess_reports_fail_without_echoing_input(self):
        self.write_inputs()
        (self.suite_dir / 'evidence-0.json').write_text(SENTINEL, encoding='utf-8')
        result = self.export(write=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        self.write_inputs()
        (self.command_dir / 'evidence-extra.json').write_text(json.dumps(self.command), encoding='utf-8')
        result = self.export(write=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_rows_are_sorted_by_cost_and_export_does_not_mutate_inputs(self):
        self.passes[0]['modules'].append(dict(self.passes[0]['modules'][0], module='slow_module', duration_seconds=999))
        self.write_inputs()
        before = {p: p.read_bytes() for d in (self.command_dir, self.suite_dir) for p in d.glob('*.json')}
        result = self.export(write=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        sources = json.loads(self.output.read_text(encoding='utf-8'))['sources']
        source = next(s for s in sources if len(s['rows']) == 2)
        self.assertEqual(source['rows'][0]['module'], 'slow_module')
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_existing_output_is_not_overwritten_and_bad_identity_is_rejected(self):
        self.output.write_text('existing', encoding='utf-8')
        result = self.export()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.output.read_text(encoding='utf-8'), 'existing')
        self.output.unlink()
        result = self.export(extra=('--run-id', '0'))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
