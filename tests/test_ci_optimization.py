"""Independent oracle: real subprocesses and workflow invariants."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_test_commands as runner


class CommandGrouping(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-ci-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contracts = self.root / 'contracts'
        self.contracts.mkdir()
        self.script = self.root / 'counter.py'
        self.script.write_text(
            'from pathlib import Path\nimport os, sys\n'
            'p = Path("count.txt")\n'
            'p.write_text(str(int(p.read_text()) + 1) if p.exists() else "1")\n'
            'print("fixture ERROR output", os.environ.get("KDD_CI_CASE", ""))\n'
            'sys.exit(int(sys.argv[1]))\n', encoding='utf8')
        self.command = '"{}" counter.py 0'.format(sys.executable)

    def contract(self, name, command=None, target='scripts/check.py'):
        command = self.command if command is None else command
        (self.contracts / name).write_text(
            '---\ntarget: {}\ntest_command: \'{}\'\n---\n'.format(target, command),
            encoding='utf8')

    def pair(self, command=None):
        self.contract('a.md', command)
        self.contract('b.md', command, 'src/product.py')

    def execute(self, **kwargs):
        return runner.run_all(str(self.contracts), str(self.root), deduplicate=True, **kwargs)

    def count(self):
        return int((self.root / 'count.txt').read_text())

    def test_one_execution_retains_contracts_scopes_and_output(self):
        self.pair()
        results = self.execute()
        self.assertEqual(self.count(), 1)
        self.assertEqual([Path(r['path']).name for r in results], ['a.md', 'b.md'])
        self.assertEqual([r['scope'] for r in results], ['infrastructure', 'product'])
        self.assertTrue(all(r['ok'] and r['exit_code'] == 0 for r in results))
        self.assertIn('fixture ERROR output', results[1]['stdout'])
        self.assertIsNone(results[0]['shared_from'])
        self.assertEqual(results[1]['shared_from'], results[0]['path'])
        self.assertGreater(results[0]['duration_seconds'], 0)
        self.assertEqual(results[1]['duration_seconds'], 0)

    def test_default_keeps_legacy_two_executions(self):
        self.pair()
        results = runner.run_all(str(self.contracts), str(self.root))
        self.assertEqual(self.count(), 2)
        self.assertTrue(all(r['shared_from'] is None for r in results))

    def test_shared_failure_fails_both_scopes(self):
        self.pair(self.command[:-1] + '3')
        results = self.execute()
        self.assertEqual(self.count(), 1)
        self.assertEqual([r['exit_code'] for r in results], [3, 3])
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(runner._print_results(results), 1)
        self.assertIn('Summary: infrastructure PASS=0 FAIL=1', output.getvalue())
        self.assertIn('Summary: product PASS=0 FAIL=1', output.getvalue())
        self.assertIn('commands=1 shared=1', output.getvalue())

    def test_timeout_and_missing_executable_propagate(self):
        (self.root / 'sleep.py').write_text('import time\ntime.sleep(3)\n', encoding='utf8')
        for command, error in [('"{}" sleep.py'.format(sys.executable), 'timeout'),
                               ('kdd-nonexistent-ci-executable', 'not_found')]:
            with self.subTest(error=error):
                self.pair(command)
                results = self.execute(timeout=0.1)
                self.assertEqual([r['error'] for r in results], [error, error])
                self.assertTrue(all(not r['ok'] for r in results))
                self.assertEqual(results[1]['shared_from'], results[0]['path'])

    def test_whitespace_and_arguments_are_not_normalized(self):
        self.contract('a.md')
        self.contract('b.md', self.command + ' ')
        self.contract('c.md', self.command[:-1] + '1')
        results = self.execute()
        self.assertEqual(self.count(), 3)
        self.assertEqual([r['ok'] for r in results], [True, True, False])

    def test_second_call_and_changed_environment_execute_again(self):
        self.pair()
        old = os.environ.get('KDD_CI_CASE')
        self.addCleanup(lambda: os.environ.pop('KDD_CI_CASE', None) if old is None
                        else os.environ.__setitem__('KDD_CI_CASE', old))
        for value in ['first', 'second']:
            os.environ['KDD_CI_CASE'] = value
            self.assertIn(value, self.execute()[0]['stdout'])
        self.assertEqual(self.count(), 2)

    def test_other_cwd_has_no_reused_result(self):
        self.pair()
        self.execute()
        other = self.root / 'other'
        other.mkdir()
        shutil.copy2(self.script, other / 'counter.py')
        results = runner.run_all(str(self.contracts), str(other), deduplicate=True)
        self.assertEqual(int((other / 'count.txt').read_text()), 1)
        self.assertTrue(all(r['ok'] for r in results))

    def test_cli_reports_count_and_shared_failure(self):
        for code in [0, 3]:
            with self.subTest(exit_code=code):
                self.pair(self.command[:-1] + str(code))
                result = subprocess.run(
                    [sys.executable, str(ROOT / 'scripts/validate_test_commands.py'),
                     str(self.contracts), str(self.root), '--deduplicate'],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, int(code != 0), result.stdout + result.stderr)
                self.assertIn('contracts=2 commands=1 shared=1', result.stdout)
                self.assertIn('SHARED', result.stdout)
        self.assertEqual(self.count(), 2)

    def test_empty_configuration_still_fails(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(['gate', str(self.contracts), str(self.root),
                                          '--deduplicate']), 1)


class WorkflowGuarantees(unittest.TestCase):
    def test_dual_os_jobs_two_identical_passes_and_gates_remain(self):
        text = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf8')
        self.assertEqual(text.count('os: [ubuntu-latest, windows-latest]'), 2)
        for name in ['validate', 'board']:
            job = text.split('\n  ' + name + ':\n', 1)[1]
            self.assertIn('runs-on: ${{ matrix.os }}', job)
        command = 'run: python -m unittest discover -s tests -p "test_*.py"'
        self.assertEqual(text.count(command), 2)
        for pass_number in [1, 2]:
            step = text.split('- name: Run unit tests ({}/2)'.format(pass_number), 1)[1]
            step = step.split('\n      - ', 1)[0]
            self.assertIn("KDD_SKIP_INIT_POST_APPLY_SUITE: '1'", step)
            self.assertIn(command, step)
        self.assertIn('run: python scripts/validate_test_commands.py "$KDD_CONTRACTS_DIR" . --timeout 600 --deduplicate', text)
        self.assertIn('- name: Check approved contract and oracle baseline', text)
        self.assertEqual(text.count("python-version: '3.11'"), 2)
        self.assertIn('run: npm test', text)
        self.assertNotIn('continue-on-error:', text)

    def test_only_native_pr_runs_can_cancel_each_other(self):
        text = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf8')
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' && !inputs.reusable_execution }}", text)
        group = next(line for line in text.splitlines() if line.startswith('  group:'))
        self.assertIn("github.event_name == 'pull_request' && !inputs.reusable_execution", group)
        self.assertIn('github.event.pull_request.number', group)
        self.assertIn('github.run_id', group)
        self.assertIn('github.run_attempt', group)
        self.assertIn("      reusable_execution:\n        type: boolean\n        default: true", text)


if __name__ == '__main__':
    unittest.main()
