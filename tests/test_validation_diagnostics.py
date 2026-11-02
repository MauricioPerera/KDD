"""Regression oracle for bounded contract diagnostics and Windows execution."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import preflight
import validate_test_commands as commands


class ValidationDiagnostics(unittest.TestCase):
    def test_each_command_has_duration_and_timeout_is_not_pass(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'task.md').write_text('---\ntest_command: "python oracle.py"\n---\n', encoding='utf-8')
            with mock.patch.object(commands, 'run_test_command', return_value={'exit_code': None, 'ok': False, 'error': 'timeout'}):
                results = commands.run_all(root, root)
            self.assertGreaterEqual(results[0]['duration_seconds'], 0)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(commands._print_results(results), 1)
            self.assertIn('TIMEOUT', output.getvalue())
            self.assertIn('duration=', output.getvalue())

    def test_preflight_outer_timeout_covers_all_individual_deadlines(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root, 'knowledge/contracts')
            directory.mkdir(parents=True)
            for n in range(3):
                (directory / ('task%d.md' % n)).write_text('---\ntest_command: "python oracle.py"\n---\n', encoding='utf-8')
            calls = {}
            def runner(name, params, repo_root='.', timeout=120):
                calls[name] = timeout
                return {'exit_code': 0, 'stdout': '', 'stderr': ''}
            self.assertTrue(preflight.run_preflight(root, runner=runner)['overall_ok'])
            self.assertGreater(calls['validate_test_commands'], 3 * 180)
            self.assertEqual(calls['validate_contracts'], 120)

    def test_cli_writes_machine_readable_timings_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as root:
            report = Path(root, 'timings.json')
            result = {'path': 'task.md', 'scope': 'product', 'test_command': 'python oracle.py', 'exit_code': 1, 'ok': False, 'error': None, 'stdout': '', 'stderr': '', 'duration_seconds': 2.5}
            with mock.patch.object(commands, 'run_all', return_value=[result]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(commands.main(['gate', root, root, '--timings-json', str(report)]), 1)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(data['results'][0]['status'], 'FAIL')
            self.assertEqual(data['results'][0]['duration_seconds'], 2.5)
            self.assertNotIn('stdout', data['results'][0])

    def test_windows_runtime_prefers_native_git_without_changing_global_path(self):
        import validation_runtime
        with tempfile.TemporaryDirectory() as root:
            native = Path(root, 'Git/cmd/git.exe')
            native.parent.mkdir(parents=True)
            native.write_bytes(b'fixture')
            supplied = {'ProgramFiles': root, 'PATH': 'C:/msys/usr/bin;C:/Python'}
            before = dict(supplied)
            result = validation_runtime.runtime_environment(supplied, platform='nt')
            self.assertEqual(result['PATH'].split(';')[0], str(native.parent))
            self.assertEqual(supplied, before)
            self.assertEqual(validation_runtime.runtime_environment(supplied, platform='posix'), before)
            upper = {'PROGRAMFILES': root, 'PATH': 'C:/msys/usr/bin;C:/Python'}
            self.assertEqual(validation_runtime.runtime_environment(upper, platform='nt')['PATH'].split(';')[0], str(native.parent))

    def test_suite_launcher_propagates_environment_and_failure(self):
        import validation_runtime
        with mock.patch.object(validation_runtime, 'runtime_environment', return_value={'PATH': 'native-git'}), mock.patch.object(validation_runtime.subprocess, 'run', return_value=mock.Mock(returncode=7)) as run:
            self.assertEqual(validation_runtime.main(['suite']), 7)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:3], [sys.executable, '-m', 'unittest'])
        self.assertEqual(kwargs['env']['PATH'], 'native-git')
        self.assertFalse(kwargs.get('shell', False))


if __name__ == '__main__':
    unittest.main()
