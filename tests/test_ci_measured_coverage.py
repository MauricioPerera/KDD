"""Validate coverage evidence and preserve the exact CI suite entrypoints."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/validate.yml'
COVERAGE_VALIDATOR = ROOT / 'scripts/validate_test_coverage_findings.py'
GOOD = {'documentType': 'kdd-test-coverage.findings', 'schemaVersion': '1.0',
        'scanId': 'integration', 'findings': []}
FINDING = {'findingId': 'cov_one', 'gapType': 'no-regression-test', 'location': 'app:accept',
           'severity': 'high', 'remediation': 'Add a real rejection test before release.',
           'source': 'coverage report', 'criticalPath': True}
COMMAND = ('run: python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . '
           '--start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" '
           '--report-dir "$RUNNER_TEMP/kdd-suite-reports"')


class CoverageFindingsSchema(unittest.TestCase):
    def run_validator(self, data):
        with tempfile.TemporaryDirectory(prefix='kdd-coverage-schema-') as directory:
            if data is not None:
                (Path(directory) / 'findings.json').write_text(
                    json.dumps(data), encoding='utf-8')
            return subprocess.run([sys.executable, str(COVERAGE_VALIDATOR), directory],
                                  capture_output=True, text=True, encoding='utf-8', timeout=15)

    def test_missing_findings_is_not_an_empty_success(self):
        document = {key: value for key, value in GOOD.items() if key != 'findings'}
        result = self.run_validator(document)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('findings', result.stderr)
        self.assertNotIn('OK:', result.stdout)

    def test_invalid_document_and_item_shapes_are_rejected(self):
        variants = [[], dict(GOOD, findings=None), dict(GOOD, findings={}),
                    dict(GOOD, findings=[1]), dict(GOOD, findings=[{'findingId': 'incomplete'}]),
                    dict(GOOD, schemaVersion='2.0'), dict(GOOD, scanId=''),
                    dict(GOOD, findings=[dict(FINDING, criticalPath='yes')])]
        for data in variants:
            with self.subTest(data=data):
                result = self.run_validator(data)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn('OK:', result.stdout)

    def test_absence_empty_valid_and_policy_violation_keep_distinct_exits(self):
        self.assertIn('PATH_MISSING', self.run_validator(None).stdout)
        self.assertEqual(self.run_validator(GOOD).returncode, 0)
        self.assertEqual(self.run_validator(dict(GOOD, findings=[FINDING])).returncode, 0)
        violation = self.run_validator(dict(GOOD, findings=[dict(FINDING, remediation='Fix')]))
        self.assertEqual(violation.returncode, 1, violation.stdout + violation.stderr)


class MeasuredCoverageWorkflow(unittest.TestCase):
    def test_only_first_trusted_pass_is_instrumented(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        first = text.split('- name: Run unit tests (1/2)\n', 1)[1].split('- name:', 1)[0]
        second = text.split('- name: Run unit tests (2/2)\n', 1)[1].split('- name:', 1)[0]
        self.assertEqual(text.count(COMMAND), 2)
        self.assertIn(COMMAND, first)
        self.assertIn(COMMAND, second)
        self.assertIn('COVERAGE_PROCESS_START', first)
        self.assertNotIn('COVERAGE_PROCESS_START', second)
        self.assertEqual(len(re.findall(r'os: \[ubuntu-latest, windows-latest\]', text)), 2)

    def test_pinned_tool_and_per_attempt_report_are_native_ci_only(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        lock = (ROOT / 'tools/ci-coverage/requirements.txt').read_text(encoding='utf-8')
        self.assertRegex(lock, r'coverage==[\d.]+')
        self.assertIn('--hash=sha256:', lock)
        requirements = {
            'Prepare Python suite coverage': ('--require-hashes', 'scripts/ci_coverage.py prepare',
                                              'tests/coverage_isolated_probe.py'),
            'Report Python suite coverage': ('scripts/ci_coverage.py report', 'GITHUB_SHA',
                                             'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'),
            'Upload Python suite coverage': ('if-no-files-found: error', 'coverage.json',
                                            'kdd-coverage-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.os }}'),
        }
        for name, snippets in requirements.items():
            with self.subTest(name=name):
                marker = '- name: ' + name + '\n'
                self.assertIn(marker, text)
                step = text.split(marker, 1)[1].split('- name:', 1)[0]
                self.assertIn('!inputs.reusable_execution', step)
                self.assertIn("github.repository == 'MauricioPerera/KDD'", step)
                for snippet in snippets:
                    self.assertIn(snippet, step)
