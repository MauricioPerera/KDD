"""Oracle for a diagnostic projection of real, pinned CI runtime reports."""
import copy
import hashlib
import json
import os
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
            'import unittest\nprint("import diagnostics")\nclass Product(unittest.TestCase):\n'
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
            self.assertEqual(len(source['rows']), 2)
            row = next(r for r in source['rows'] if r['module'] == 'test_product')
            self.assertEqual(set(row), {'module', 'duration_seconds', 'tests_run', 'exit_code'})
            self.assertEqual(row['module'], 'test_product')
            self.assertEqual(row['tests_run'], 1)
            self.assertEqual(row['exit_code'], 0)
            original = next(s for s in self.passes if s['duration_seconds'] == source['duration_seconds'])
            metric = next(m for m in original['modules'] if m['module'] == 'test_product')
            self.assertEqual(row['duration_seconds'], metric['duration_seconds'])
            diagnostics = next(r for r in source['rows'] if r['module'] == 'controller diagnostics')
            self.assertEqual(diagnostics['tests_run'], 0)
            self.assertEqual(diagnostics['exit_code'], 0)
            self.assertEqual(diagnostics['duration_seconds'],
                next(m for m in original['modules'] if m['module'] == 'controller diagnostics')['duration_seconds'])
        command = next(s for s in sources if s['kind'] == 'commands')
        self.assertIsNone(command['duration_seconds'], 'A sum of concurrent commands is not elapsed wall time')
        self.assertEqual(command['rows'][0], {'contract': 'knowledge/contracts/fixture.md',
            'scope': 'product', 'duration_seconds': self.command['results'][0]['duration_seconds'],
            'exit_code': 0, 'recorded_ok': True, 'shared_from': None})

    def test_each_suite_source_hash_identifies_its_own_receipt_metrics(self):
        self.passes[0]['duration_seconds'] = 11.25
        self.passes[1]['duration_seconds'] = 42.5
        report = self.document()

        def metrics(duration, ok, modules):
            return duration, ok, {
                row['module']: (row['duration_seconds'], row['tests_run'], row['exit_code'])
                for row in modules
            }

        expected = {}
        for path in self.suite_dir.glob('evidence-*.json'):
            raw = path.read_bytes()
            receipt = json.loads(raw)
            expected[hashlib.sha256(raw).hexdigest()] = metrics(
                receipt['duration_seconds'], receipt['ok'], receipt['modules'])
        actual = {
            source['source_sha256']: metrics(
                source['duration_seconds'], source['recorded_ok'], source['rows'])
            for source in report['sources'] if source['kind'] == 'suite'
        }
        self.assertEqual(actual, expected)

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
        failed_module = next(row for row in self.passes[0]['modules']
                             if row['module'] == 'test_product')
        failed_module['exit_code'] = 1
        report = self.document()
        command = next(s for s in report['sources'] if s['kind'] == 'commands')
        self.assertFalse(command['recorded_ok'])
        self.assertIsNone(command['rows'][0]['exit_code'])
        self.assertFalse(command['rows'][0]['recorded_ok'])
        self.assertIn(False, [s['recorded_ok'] for s in report['sources'] if s['kind'] == 'suite'])
        failed_suite = next(source for source in report['sources']
                            if source['kind'] == 'suite' and source['recorded_ok'] is False)
        recorded_module = next(row for row in failed_suite['rows'] if row['module'] == 'test_product')
        self.assertEqual(recorded_module['exit_code'], 1)

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

    def test_unknown_report_versions_and_invalid_counters_are_rejected(self):
        original = copy.deepcopy(self.passes)
        for value in (2, '1', True, None):
            with self.subTest(version=value):
                self.passes = copy.deepcopy(original)
                self.passes[0]['version'] = value
                self.rejected()
        for value in (-1, True, 1.5, None):
            with self.subTest(tests_run=value):
                self.passes = copy.deepcopy(original)
                self.passes[0]['modules'][0]['tests_run'] = value
                self.rejected()

    def test_duplicate_json_keys_are_rejected_without_publishing(self):
        self.write_inputs()
        path = self.suite_dir / 'evidence-0.json'
        text = path.read_text(encoding='utf-8')
        path.write_text(text.replace('{', '{"version": 1,', 1), encoding='utf-8')
        result = self.export(write=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())
        self.write_inputs()
        text = path.read_text(encoding='utf-8')
        label = '"duration_seconds":'
        path.write_text(text.replace(label, '"duration_seconds": 0, ' + label, 1), encoding='utf-8')
        result = self.export(write=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_invalid_source_command_durations_statuses_and_exits_are_rejected(self):
        suites, commands = copy.deepcopy(self.passes), copy.deepcopy(self.command)
        for target, key, value in (
                ('suite', 'duration_seconds', True), ('suite', 'duration_seconds', float('inf')),
                ('command-row', 'duration_seconds', -1), ('command-row', 'duration_seconds', True),
                ('command-row', 'exit_code', True), ('suite-row', 'exit_code', False),
                ('suite', 'ok', 'true'), ('command', 'version', 2), ('command-row', 'ok', 1)):
            with self.subTest(target=target, key=key, value=value):
                self.passes, self.command = copy.deepcopy(suites), copy.deepcopy(commands)
                selected = {'suite': self.passes[0], 'command': self.command,
                            'command-row': self.command['results'][0],
                            'suite-row': self.passes[0]['modules'][0]}[target]
                selected[key] = value
                self.rejected()

    def test_missing_directories_publish_no_fabricated_sources(self):
        self.command_dir.rmdir(); self.suite_dir.rmdir()
        result = self.export(write=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertFalse(report['complete'])
        self.assertEqual(report['sources'], [])
        self.assertEqual(report['missing'], ['commands-report', 'suite-report-1', 'suite-report-2'])

    def test_redirected_report_directory_is_rejected_on_both_platforms(self):
        self.write_inputs()
        target = self.suite_dir.with_name('real-suites')
        self.suite_dir.rename(target)
        if os.name == 'nt':
            self.checked(['cmd', '/d', '/c', 'mklink', '/J', str(self.suite_dir), str(target)])
        else:
            self.suite_dir.symlink_to(target, target_is_directory=True)
        try:
            result = self.export(write=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.output.exists())
        finally:
            if os.name == 'nt':
                self.suite_dir.rmdir()
            else:
                self.suite_dir.unlink()

    @unittest.skipIf(os.name == 'nt', 'Windows directory-redirection coverage uses an unprivileged junction')
    def test_symlinked_report_file_is_rejected(self):
        self.write_inputs()
        path = self.suite_dir / 'evidence-0.json'
        target = self.base / 'linked-report.json'
        path.rename(target)
        path.symlink_to(target)
        result = self.export(write=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

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
        source = next(s for s in sources if len(s['rows']) == 3)
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
