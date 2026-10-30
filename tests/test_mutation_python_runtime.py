"""A bare Python alias must execute mutation controls in the active runtime."""
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
import mutation_audit

class MutationPythonRuntime(unittest.TestCase):
    def test_bare_alias_selects_the_current_interpreter(self):
        for alias in ('python', 'python3', 'python.exe'):
            with self.subTest(alias=alias):
                self.assertEqual(mutation_audit._command(alias+' -m unittest tests.test_app'),
                                 [sys.executable, '-m', 'unittest', 'tests.test_app'])

    def test_an_explicit_executable_is_preserved(self):
        self.assertEqual(mutation_audit._command('"'+sys._base_executable+'" -m unittest tests.test_app')[0],
                         sys._base_executable)

    def test_real_isolated_runtime_wins_over_a_different_python_on_path(self):
        with tempfile.TemporaryDirectory(prefix='kdd-mutation-runtime-') as directory:
            area = Path(directory)
            environment = (area / 'venv').resolve()
            venv.EnvBuilder(with_pip=False).create(environment)
            python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            project = area / 'project'
            for name in ('src', 'tests'):
                (project / name).mkdir(parents=True, exist_ok=True)
                (project / name / '__init__.py').write_text('', encoding='utf-8')
            (project / 'src/app.py').write_text('def is_one(value):\n if value == 1:\n  return True\n return False\n', encoding='utf-8')
            oracle = ('import unittest,sys\nfrom src.app import is_one\n'
                      'class Oracle(unittest.TestCase):\n'
                      ' def test_runtime_and_behavior(self):\n'
                      '  self.assertEqual(sys.prefix, '+repr(str(environment)) + ')\n'
                      '  self.assertTrue(is_one(1))\n  self.assertFalse(is_one(2))\n')
            (project / 'tests/test_app.py').write_text(oracle, encoding='utf-8')
            contract = project / 'contract.md'
            contract.write_text("---\ntarget: src/app.py\ntests: tests/test_app.py\ntest_command: python -m unittest tests.test_app\n---\n", encoding='utf-8')
            env = dict(os.environ, PYTHONUTF8='1')
            env['PATH'] = str(Path(sys._base_executable).parent) + os.pathsep + env.get('PATH', '')
            result = subprocess.run([str(python), str(ROOT / 'scripts/mutation_audit.py'), str(contract),
                                     '--repo-root', str(project), '--strict'], cwd=project, env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('3 detected, 0 survived, 0 inconclusive', result.stdout)
            self.assertIn('control original: PASS', result.stdout)
            self.assertIn('control copy: PASS', result.stdout)
