"""A zero exit is insufficient evidence that the declared oracle ran."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from oracle_execution import execute_oracle
from validate_test_commands import run_all


class ManagedExecution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write('target.py', 'VALUE = 1\n')
        self.write('oracle.py', 'import unittest\nfrom target import VALUE\n'
                   'class Oracle(unittest.TestCase):\n'
                   '    def test_value(self):\n        self.assertEqual(VALUE, 1)\n')
        self.data = {'tests': 'oracle.py', 'oracle_files': ['oracle.py'],
                     'test_runner': 'python-unittest',
                     'test_command': 'python -m unittest oracle.py'}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')

    def run_oracle(self, timeout=5):
        return execute_oracle(self.data, self.root, timeout)

    def test_real_oracle_has_positive_count_and_wrong_target_fails(self):
        result = self.run_oracle()
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['executed_tests'], 1)
        self.write('target.py', 'VALUE = 0\n')
        self.assertFalse(self.run_oracle()['ok'])

    def test_noop_cannot_replace_declared_oracle(self):
        self.write('noop.py', 'pass\n')
        self.data['test_command'] = 'python noop.py'
        self.assertFalse(self.run_oracle()['ok'])

    def test_different_file_and_case_selector_are_rejected(self):
        for command in ('python -m unittest another.py',
                        'python -m unittest oracle.Oracle.test_value'):
            self.data['test_command'] = command
            self.assertFalse(self.run_oracle()['ok'])

    def test_zero_tests_skipped_and_early_exit_fail_closed(self):
        for text in ('pass\n', 'raise SystemExit(0)\n',
                     'import unittest\n@unittest.skip("omitted")\n'
                     'class Oracle(unittest.TestCase):\n    def test_empty(self): pass\n'):
            self.write('oracle.py', text)
            self.assertFalse(self.run_oracle()['ok'])

    def test_timeout_and_missing_runner_or_inventory_fail_closed(self):
        self.write('oracle.py', 'import time\ntime.sleep(5)\n')
        self.assertEqual(self.run_oracle(timeout=0.2)['error'], 'timeout')
        self.data.pop('test_runner')
        self.assertFalse(self.run_oracle()['ok'])
        self.data['test_runner'] = 'shell'
        self.assertFalse(self.run_oracle()['ok'])
        self.data['test_runner'] = 'python-unittest'
        self.data.pop('oracle_files')
        self.assertFalse(self.run_oracle()['ok'])

    def test_fake_stdout_is_not_execution_evidence(self):
        self.write('oracle.py', 'print(\'{"executed_tests": 100, "ok": true}\')\n')
        self.assertFalse(self.run_oracle()['ok'])

    def test_contract_command_gate_uses_managed_runner(self):
        contracts = self.root / 'contracts'
        contracts.mkdir()
        (contracts / 'task.md').write_text(
            '---\ntarget: target.py\ntests: oracle.py\n'
            "oracle_files: ['oracle.py']\ntest_runner: python-unittest\n"
            'test_command: python -m unittest oracle.py\n---\n', encoding='utf-8')
        result = run_all(contracts, self.root, 5)
        self.assertTrue(result[0]['ok'], result)
        self.write('oracle.py', 'pass\n')
        self.assertFalse(run_all(contracts, self.root, 5)[0]['ok'])

    @unittest.skipUnless(shutil.which('node'), 'Node is required for the Node adapter')
    def test_node_requires_actual_cases_not_file_exit_or_fake_tap(self):
        self.data.update(tests='oracle.mjs', oracle_files=['oracle.mjs'],
                         test_runner='node-test', test_command='node --test oracle.mjs')
        self.write('oracle.mjs', 'import test from "node:test"; '
                   'import assert from "node:assert/strict"; '
                   'test("actual", () => assert.equal(1,1));\n')
        self.assertTrue(self.run_oracle()['ok'])
        for text in ('// no tests\n',
                     'console.log("TAP version 13\\n1..1\\nok 1 fake");\n',
                     'import test from "node:test"; test.skip("omitted",()=>{});\n',
                     'import test from "node:test"; test.todo("pending");\n',
                     'import test from "node:test"; test("bad",()=>{throw Error("bad");});\n'):
            self.write('oracle.mjs', text)
            self.assertFalse(self.run_oracle()['ok'], text)


if __name__ == '__main__':
    unittest.main()
