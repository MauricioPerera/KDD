"""Real command reports drive the exact workflow timing summary."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml
from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_test_commands import run_all


class CommandTiming(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-command-metric-')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.root = self.area / 'project'; self.root.mkdir()
        self.contracts = self.root / 'knowledge/contracts'; self.contracts.mkdir(parents=True)
        (self.root / 'tests').mkdir(); (self.root / 'tests/__init__.py').write_text('')
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/init_project.py').write_text('def init_project(): return 0\n')
        self.marker = self.area / 'executed.txt'
        oracle = ('import os,time,unittest\nfrom pathlib import Path\n'
                  'class Product(unittest.TestCase):\n def test_run(self):\n'
                  '  time.sleep(0.02)\n'
                  '  Path(%r).write_text("executed",encoding="utf-8")\n'
                  '  print(\'KDD_INIT_TIMING {"ok":true,"duration_seconds":0.0001}\')\n'
                  '  self.assertNotEqual(os.environ.get("KDD_METRIC_FAIL"),"1")\n') % str(self.marker)
        (self.root / 'tests/test_init_project.py').write_text(oracle, encoding='utf-8')
        text = """---
type: 'Task Contract'
title: 'Synthetic init'
description: 'Independent command timing fixture.'
tags: ['test']
task: init-project
intent: 'Run a real test command.'
target: scripts/init_project.py
signature: 'def init_project():'
test_command: 'python -m unittest tests/test_init_project.py'
budget:
  cyclomatic_max: 3
tests: tests/test_init_project.py
tests_sha256: 'SEAL'
touch_only: ['scripts/init_project.py']
deps_allowed: ['stdlib']
forbids: ['network']
---
## Intent
Run the synthetic oracle.
## Interface
Return a real process outcome.
## Invariants
Preserve the exit and elapsed duration.
## Examples
- A passing oracle exits zero.
- A failing oracle exits nonzero.
## Do / Don't
Do measure real execution.
## Tests
The real unittest writes a marker.
## Constraints
PARAR y reportar si the fixture cannot execute.
""".replace('SEAL', hashlib.sha256(oracle.encode()).hexdigest())
        (self.contracts / 'init-project.md').write_text(text, encoding='utf-8')
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.root)], check=True,
                       capture_output=True, timeout=30)
        configure_git(self.root, {'user.name': 'Timing fixture',
                      'user.email': 'timing@example.invalid'}, ephemeral=True)
        self.git('add', '-A'); self.git('commit', '-qm', 'Synthetic timing baseline')
        self.ref = self.git('rev-parse', 'HEAD')
        self.runner = self.area / 'runner'
        self.reports = self.runner / 'kdd-command-reports'; self.reports.mkdir(parents=True)
        self.file = self.reports / 'evidence-fixture.json'
        self.environment = dict(os.environ, RUNNER_TEMP=str(self.runner),
            GITHUB_RUN_ID='12345', GITHUB_RUN_ATTEMPT='2', GITHUB_SHA=self.ref,
            KDD_TRUSTED_RUNTIME_REF=self.ref, PYTHONUTF8='1')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
            text=True, encoding='utf-8', stderr=subprocess.PIPE, timeout=30).strip()

    def report(self, failed=False):
        with patch.dict(os.environ, {'KDD_METRIC_FAIL': '1' if failed else '0'}):
            results = run_all(str(self.contracts), str(self.root), timeout=30)
        self.assertEqual(len(results), 1)
        self.assertEqual(self.marker.read_text(encoding='utf-8'), 'executed')
        data = {'version': 1, 'ok': not failed, 'results': results, 'contracts': 1,
                'exclusive_commands': [], 'trusted_runtime_ref': self.ref}
        self.write_report(data)
        return data

    def write_report(self, data):
        self.file.write_text(json.dumps(data), encoding='utf-8')

    def step(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8'))
        steps = workflow['jobs']['validate']['steps']
        matches = [s for s in steps if s.get('name') == 'Report init command duration']
        self.assertEqual(len(matches), 1, 'Missing unique command duration step')
        return matches[0], steps

    def summarize(self):
        step, _ = self.step()
        self.assertEqual(step.get('shell'), 'python')
        return subprocess.run([sys.executable, '-c', step['run']], cwd=self.root,
            env=self.environment, capture_output=True, text=True, encoding='utf-8', timeout=30)

    def metric(self, process):
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        rows = [json.loads(s[len('KDD_INIT_TIMING '):]) for s in process.stdout.splitlines()
                if s.startswith('KDD_INIT_TIMING ')]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_existing_gate_measures_the_real_command(self):
        data = self.report()
        row = data['results'][0]
        self.assertTrue(row['ok'])
        self.assertEqual(row['exit_code'], 0)
        self.assertIsNone(row['shared_from'])
        self.assertTrue(math.isfinite(row['duration_seconds']))
        self.assertGreater(row['duration_seconds'], 0.02)
        self.assertIn('KDD_INIT_TIMING', row['stdout'])

    def test_workflow_always_reports_native_runs_before_the_suites(self):
        step, steps = self.step()
        condition = str(step.get('if', ''))
        self.assertIn('always()', condition)
        self.assertIn('!inputs.reusable_execution', condition)
        self.assertIn("github.repository == 'MauricioPerera/KDD'", condition)
        self.assertNotIn('continue-on-error', step)
        names = [s.get('name') for s in steps]
        self.assertLess(names.index("Run each contract's test_command"), names.index(step['name']))
        self.assertLess(names.index(step['name']), names.index('Run unit tests (1/2)'))

    def test_real_duration_is_bound_to_run_and_ignores_child_stdout(self):
        data = self.report(); metric = self.metric(self.summarize())
        self.assertEqual(metric, {'schema_version': 1, 'run_id': '12345', 'run_attempt': '2',
            'head_sha': self.ref, 'trusted_runtime_ref': self.ref,
            'contract': 'knowledge/contracts/init-project.md',
            'duration_seconds': data['results'][0]['duration_seconds'],
            'ok': True, 'exit_code': 0, 'error': None})

    def test_real_failure_preserves_exit_and_duration(self):
        data = self.report(failed=True); metric = self.metric(self.summarize())
        self.assertFalse(metric['ok'])
        self.assertEqual(metric['exit_code'], data['results'][0]['exit_code'])
        self.assertNotEqual(metric['exit_code'], 0)
        self.assertEqual(metric['duration_seconds'], data['results'][0]['duration_seconds'])

    def test_missing_or_multiple_reports_fail_closed(self):
        self.assertNotEqual(self.summarize().returncode, 0)
        data = self.report()
        (self.reports / 'evidence-other.json').write_text(json.dumps(data), encoding='utf-8')
        self.assertNotEqual(self.summarize().returncode, 0)

    def test_invalid_duration_and_version_fail_closed(self):
        original = self.report()
        for value in (True, -1, float('nan'), float('inf'), '3'):
            with self.subTest(duration=repr(value)):
                data = copy.deepcopy(original); data['results'][0]['duration_seconds'] = value
                self.write_report(data)
                self.assertNotEqual(self.summarize().returncode, 0)
        for version in (99, True, '1'):
            with self.subTest(version=repr(version)):
                data = copy.deepcopy(original); data['version'] = version; self.write_report(data)
                self.assertNotEqual(self.summarize().returncode, 0)

    def test_wrong_runtime_missing_duplicate_or_shared_init_fail_closed(self):
        original = self.report()
        variants = []
        data = copy.deepcopy(original); data['trusted_runtime_ref'] = '0' * 40; variants.append(data)
        data = copy.deepcopy(original); data['results'] = []; variants.append(data)
        data = copy.deepcopy(original); data['results'] *= 2; variants.append(data)
        data = copy.deepcopy(original); data['results'][0]['shared_from'] = 'other.md'; variants.append(data)
        data = copy.deepcopy(original); data['results'][0]['test_command'] = 'echo fake'; variants.append(data)
        data = copy.deepcopy(original); data['results'][0]['scope'] = 'product'; variants.append(data)
        data = copy.deepcopy(original); data['results'][0]['ok'] = 'true'; variants.append(data)
        data = copy.deepcopy(original); data['results'][0]['exit_code'] = 7; variants.append(data)
        for index, data in enumerate(variants):
            with self.subTest(case=index):
                self.write_report(data)
                self.assertNotEqual(self.summarize().returncode, 0)


if __name__ == '__main__':
    unittest.main()
