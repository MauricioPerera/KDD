"""Frozen acceptance oracle for the native level-2 adapter."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import native_level2 as native


def fixture(root):
    (root / 'src').mkdir()
    (root / 'tests').mkdir()
    (root / 'src/add.py').write_text('def add(a: int, b: int) -> int:\n    return a + b\n')
    test = root / 'tests/check.py'
    test.write_bytes(b'from src.add import add\r\nassert add(2, 3) == 5\r\n')
    digest = hashlib.sha256(test.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    contract = root / 'add.md'
    contract.write_text('''---
type: 'Task Contract'
title: 'Sumar enteros'
description: 'Sumar dos enteros mediante una funcion pura verificable.'
tags: ['test']
task: add
intent: 'Sumar enteros.'
target: src/add.py
signature: 'def add(a: int, b: int) -> int'
test_command: 'python -m tests.check'
budget:
  cyclomatic_max: 3
  nesting_max: 1
tests: tests/check.py
tests_sha256: 'DIGEST'
touch_only: ['src/add.py']
deps_allowed: []
forbids: ['network']
---
## Intent
Sumar enteros.
## Interface
add(a, b) devuelve un entero.
## Invariants
- Resultado igual a la suma.
## Examples
- add(2, 3) -> 5
- add(0, 0) -> 0
## Do / Don't
- DO: devolver suma. DON'T: llamar red.
## Tests
tests/check.py comprueba add con asserts.
## Constraints
PARAR y reportar si el contrato no es verificable.
'''.replace('DIGEST', digest), encoding='utf-8')
    return contract


class NativeLevel2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = fixture(self.root)

    def test_prepare_preserves_command_and_sets_repo_cwd(self):
        prepared = native.prepare(self.contract, self.root)
        self.assertEqual(prepared['metadata']['test_command'], 'python -m tests.check')
        self.assertEqual(prepared['metadata']['test_cwd'], '.')
        self.assertEqual(prepared['metadata']['budget']['params_max'], 5)
        self.assertTrue(prepared['metadata']['require_test_approval'])

    def test_crlf_seal_is_checked_then_translated_to_raw(self):
        prepared = native.prepare(self.contract, self.root)
        raw = hashlib.sha256((self.root / 'tests/check.py').read_bytes()).hexdigest()
        self.assertEqual(prepared['metadata']['tests_sha256'], raw)
        self.assertNotEqual(raw, prepared['tests_sha256_lf'])

    def test_wrong_engine_revision_rejected(self):
        with patch.object(native, '_git', return_value='0' * 40):
            with self.assertRaises(ValueError):
                native.verify_engine(self.root)

    def test_dirty_engine_rejected(self):
        with patch.object(native, '_git', side_effect=[native.ENGINE_COMMIT, ' M runners/task_gate.py']):
            with self.assertRaises(ValueError):
                native.verify_engine(self.root)

    def test_changed_oracle_fails_before_execution(self):
        (self.root / 'tests/check.py').write_text('assert False\n')
        with patch.object(native, '_invoke') as invoke:
            result = native.run_level2(self.contract, self.root, self.root / 'missing')
        self.assertFalse(result['ok'])
        invoke.assert_not_called()

    def test_unsupported_language_and_group_fail_closed(self):
        original = self.contract.read_text(encoding='utf-8')
        for field in ('language: rust', 'kind: group'):
            self.contract.write_text(original.replace('task: add', 'task: add\n' + field), encoding='utf-8')
            with self.assertRaises(ValueError):
                native.prepare(self.contract, self.root)

    def test_budget_over_cap_is_not_downgraded_to_warning(self):
        raw = self.contract.read_text(encoding='utf-8').replace('nesting_max: 1', 'nesting_max: 1\n  params_max: 6')
        self.contract.write_text(raw, encoding='utf-8')
        with self.assertRaises(ValueError):
            native.prepare(self.contract, self.root)

    def test_paths_must_stay_in_root(self):
        raw = self.contract.read_text(encoding='utf-8').replace('src/add.py', '../outside.py')
        self.contract.write_text(raw, encoding='utf-8')
        with self.assertRaises(ValueError):
            native.prepare(self.contract, self.root)

    def test_missing_engine_is_not_pass_or_skip(self):
        result = native.run_level2(self.contract, self.root, self.root / 'missing')
        self.assertFalse(result['ok'])
        self.assertEqual(result['verdict'], 'ERROR')

    def test_pass_evidence_and_temporary_export_cleanup(self):
        original = self.contract.read_bytes()
        def invoke(command, timeout, cwd):
            exported = Path(command[-1])
            self.assertTrue(exported.exists())
            self.assertEqual(exported.parent, self.root)
            return {'verdict': 'PASS', 'stage': 'all', 'metrics': {'cyclomatic': 1}}
        with patch.object(native, 'verify_engine', return_value=native.ENGINE_COMMIT), patch.object(native, '_invoke', side_effect=invoke):
            result = native.run_level2(self.contract, self.root, self.root / 'engine')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['engine_commit'], native.ENGINE_COMMIT)
        self.assertIn('contract_sha256', result)
        self.assertEqual(self.contract.read_bytes(), original)
        self.assertEqual(list(self.root.glob('*.gate.md')), [])

    def test_gate_failure_stays_failure(self):
        with patch.object(native, 'verify_engine', return_value=native.ENGINE_COMMIT), patch.object(native, '_invoke', return_value={'verdict': 'FAIL', 'stage': 'gate2-complexity'}):
            result = native.run_level2(self.contract, self.root, self.root / 'engine')
        self.assertFalse(result['ok'])
        self.assertEqual(result['verdict'], 'FAIL')

    def test_mutation_during_execution_invalidates_pass(self):
        def invoke(*args):
            (self.root / 'src/add.py').write_text('def add(a, b): return 0\n')
            return {'verdict': 'PASS', 'stage': 'all'}
        with patch.object(native, 'verify_engine', return_value=native.ENGINE_COMMIT), patch.object(native, '_invoke', side_effect=invoke):
            result = native.run_level2(self.contract, self.root, self.root / 'engine')
        self.assertFalse(result['ok'])
        self.assertEqual(result['stage'], 'inputs-changed')

    def test_timeout_has_no_success_evidence(self):
        with patch.object(native, 'verify_engine', return_value=native.ENGINE_COMMIT), patch.object(native, '_invoke', side_effect=TimeoutError):
            result = native.run_level2(self.contract, self.root, self.root / 'engine', timeout=1)
        self.assertEqual(result['verdict'], 'TIMEOUT')
        self.assertFalse(result['ok'])
        self.assertEqual(list(self.root.glob('*.gate.md')), [])

    def test_invalid_timeout_rejected(self):
        for timeout in (0, -1, float('nan'), float('inf'), True):
            result = native.run_level2(self.contract, self.root, self.root / 'engine', timeout=timeout)
            self.assertFalse(result['ok'])

    def test_real_process_timeout(self):
        with self.assertRaises(TimeoutError):
            native._invoke([sys.executable, '-c', 'import time; time.sleep(20)'], .1, self.root)

    def test_process_invalid_json_is_error(self):
        with self.assertRaises(ValueError):
            native._invoke([sys.executable, '-c', 'print("not json")'], 5, self.root)

    def test_cli_failure_exit_and_json(self):
        result = subprocess.run([sys.executable, '-m', 'scripts.native_level2', str(self.contract),
                                 '--repo-root', str(self.root), '--engine-root', str(self.root / 'missing')],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
