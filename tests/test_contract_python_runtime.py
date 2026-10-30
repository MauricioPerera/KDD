"""Legacy contract commands keep the caller's Python environment."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_test_commands as commands

class ContractPythonRuntime(unittest.TestCase):
    def test_generic_aliases_use_the_active_interpreter(self):
        for alias in ('python', 'python3', 'python.exe'):
            with self.subTest(alias=alias):
                self.assertEqual(commands._command_tokens(alias+' -m unittest test_oracle'),
                                 [sys.executable, '-m', 'unittest', 'test_oracle'])

    def test_explicit_executable_keeps_its_identity(self):
        self.assertEqual(commands._command_tokens('"'+sys._base_executable+'" -m unittest test_oracle')[0],
                         sys._base_executable)

    def test_real_venv_command_does_not_escape_to_python_on_path(self):
        with tempfile.TemporaryDirectory(prefix='kdd-contract-runtime-') as directory:
            root = Path(directory).resolve()
            environment = root / 'venv'
            venv.EnvBuilder(with_pip=False).create(environment)
            python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            program = ("import sys,json;sys.path.insert(0,sys.argv[1]);"
                       "from validate_test_commands import run_test_command;"
                       "r=run_test_command('python -c \"import sys,json;print(json.dumps(sys.prefix))\"', '.', 10, True);"
                       "print(json.dumps(r))")
            env = dict(os.environ, PYTHONUTF8='1')
            env['PATH'] = str(Path(sys._base_executable).parent)+os.pathsep+env.get('PATH','')
            result = subprocess.run([str(python), '-c', program, str(ROOT/'scripts')], cwd=root, env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report['ok'], report)
            self.assertEqual(Path(json.loads(report['stdout'])).resolve(), environment.resolve())
