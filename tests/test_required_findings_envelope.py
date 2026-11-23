"""Run standalone findings validators and the required-evidence summary on real JSON."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ('privacy', 'accessibility', 'dependency-eol', 'observability')


class RequiredFindingsEnvelope(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='kdd-required-findings-')
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.artifact = self.directory / 'findings.json'
        self.env = dict(os.environ, PYTHONUTF8='1')
        self.env.pop('GITHUB_STEP_SUMMARY', None)

    def run_cli(self, script, *args, env):
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args],
                              stdin=subprocess.DEVNULL, cwd=ROOT, env=env, capture_output=True,
                              text=True, encoding='utf-8', timeout=30)

    def summary(self, layer, data, required=True):
        self.artifact.write_text(json.dumps(data), encoding='utf-8')
        prefix = 'KDD_' + layer.replace('-', '_').upper()
        env = {**self.env, prefix + '_SCAN_DIR': str(self.directory),
               'KDD_REQUIRED_EVIDENCE': layer if required else ''}
        detected = self.run_cli('validate_' + layer.replace('-', '_') + '_findings.py',
                                str(self.directory), env=env)
        env[prefix + '_OUTCOME'] = 'success' if detected.returncode == 0 else 'failure'
        result = self.run_cli('optional_evidence.py', 'summary', '--layers', layer, env=env)
        return detected, result

    def artifact_data(self, layer):
        schema = ROOT / 'knowledge/data_models' / layer / 'findings.schema.json'
        kinds = json.loads(schema.read_text(encoding='utf-8'))['properties']
        return dict(documentType=kinds['documentType']['const'],
                    schemaVersion=kinds['schemaVersion']['const'],
                    scanId='fixture-local-scan', findings=[])

    def test_required_layer_rejects_missing_required_metadata_even_if_validator_exits_zero(self):
        for layer in LAYERS:
            source = self.artifact_data(layer)
            for key in ('schemaVersion', 'scanId', 'findings'):
                with self.subTest(layer=layer, missing=key):
                    data = {k: v for k, v in source.items() if k != key}
                    validator, result = self.summary(layer, data)
                    self.assertEqual(result.returncode, 1, (validator.stdout, result.stdout, result.stderr))
                    self.assertIn(f'FAIL [{layer}]', result.stdout)

    def test_required_layer_accepts_an_explicit_empty_scan_with_required_metadata(self):
        for layer in LAYERS:
            with self.subTest(layer=layer):
                validator, result = self.summary(layer, self.artifact_data(layer))
                self.assertEqual(validator.returncode, 0, validator.stdout + validator.stderr)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f'PASS [{layer}]', result.stdout)

    def test_required_layer_rejects_wrong_version_blank_scan_and_null_findings(self):
        for layer in LAYERS:
            for key, value in (('schemaVersion', '0.9'), ('scanId', '   '), ('findings', None)):
                with self.subTest(layer=layer, invalid=key):
                    data = {**self.artifact_data(layer), key: value}
                    validator, result = self.summary(layer, data)
                    self.assertEqual(result.returncode, 1, (validator.stdout, result.stdout, result.stderr))
                    self.assertIn(f'FAIL [{layer}]', result.stdout)
