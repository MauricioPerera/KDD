"""Expensive integration contracts need an explicit, bounded time budget."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_test_commands as commands
from oracle_execution import declared_timeout
from preflight import contract_gate_timeout, _check_test_command


class ContractTimeouts(unittest.TestCase):
    def test_contract_preflight_does_not_downgrade_a_managed_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'oracle.py').write_text('pass\n')
            (root / 'noop.py').write_text('pass\n')
            outcome = _check_test_command(str(root), {
                'tests': 'oracle.py', 'oracle_files': ['oracle.py'],
                'test_runner': 'python-unittest', 'test_command': 'python noop.py'})
            self.assertNotEqual(outcome['exit_code'], 0)

    def test_declared_timeout_is_bounded_and_legacy_fallback_is_preserved(self):
        self.assertEqual(declared_timeout({}, 7), 7)
        self.assertEqual(declared_timeout({'test_timeout': 300}, 7), 300)
        self.assertEqual(declared_timeout({'test_timeout': '300'}, 7), 300)
        for value in (0, -1, True, '3e2', 1.2, 3601):
            with self.subTest(value=value), self.assertRaises(ValueError):
                declared_timeout({'test_timeout': value}, 7)

    def test_gate_uses_declared_deadline_and_preflight_budgets_for_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'knowledge/contracts'
            folder.mkdir(parents=True)
            (folder / 'slow.md').write_text(
                '---\ntest_command: python slow.py\ntest_timeout: 300\n---\n')
            with patch.object(commands, 'run_test_command', return_value={
                    'exit_code': 0, 'ok': True, 'error': None}) as run:
                self.assertTrue(commands.run_all(folder, root, 7)[0]['ok'])
                self.assertEqual(run.call_args.kwargs['timeout'], 300)
            self.assertEqual(contract_gate_timeout(str(root)), 330)

    def test_invalid_deadline_never_runs_the_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bad.md').write_text(
                '---\ntest_command: python bad.py\ntest_timeout: -1\n---\n')
            with patch.object(commands, 'run_test_command') as run:
                result = commands.run_all(root, root)
                self.assertFalse(result[0]['ok'])
                self.assertIn('test_timeout', result[0]['error'])
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
