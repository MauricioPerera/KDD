"""Oraculo congelado del gate de ejecucion de test_command (Contrato: test-command-gate).

Fija el comportamiento de ``scripts/validate_test_commands.py``: el unico gate
de este repo cuyo 'forbids' NO incluye 'subprocess', porque su intent es
literalmente ejecutar el ``test_command`` declarado en cada contrato y leer
su exit code. Ver knowledge/contracts/test-command-gate.md, seccion
'Por que este gate rompe la convencion forbids: subprocess'.

  API:
    ``extract_test_command(text) -> str|None`` — valor de la clave
      ``test_command`` en el frontmatter YAML de un contrato (comillas simples
      o dobles). None si la clave no esta presente.
    ``collect_contracts(directory) -> [{'path','test_command'}]`` — un item
      por cada ``*.md`` de ``directory`` que:
        - NO empieza con ``TEMPLATE-`` (no es un contrato real).
        - tiene una clave ``test_command`` no vacia en su frontmatter.
      Ordenado por ``path`` ascendente. Archivos sin ``test_command`` o con
      prefijo ``TEMPLATE-`` se excluyen en silencio (no son error del gate:
      la ausencia de la clave ya la reporta ``validate_contracts.py``).
    ``run_test_command(cmd, cwd, timeout) -> {'exit_code','ok','error'}``
      Ejecuta ``cmd`` (string) partido con ``shlex.split`` via
      ``subprocess.run``, cwd=cwd, con el timeout (segundos) dado.
        - Exit 0 -> ``{'exit_code': 0, 'ok': True, 'error': None}``.
        - Exit !=0 -> ``{'exit_code': N, 'ok': False, 'error': None}``.
        - Timeout -> ``{'exit_code': None, 'ok': False, 'error': 'timeout'}``.
        - Comando no encontrado (FileNotFoundError) ->
          ``{'exit_code': None, 'ok': False, 'error': 'not_found'}``.
    ``run_all(contracts_dir, repo_root, timeout=120) -> [{'path',
      'test_command','exit_code','ok','error'}]`` — un item por contrato de
      ``collect_contracts(contracts_dir)``, cada uno corrido con
      ``run_test_command`` desde ``repo_root``. Mismo orden que
      ``collect_contracts``.
    ``main(argv) -> int`` — ``argv[1]``=contracts_dir (default
      'knowledge/contracts'), ``argv[2]``=repo_root (default '.'). Imprime,
      por linea, ``"PASS <path>"`` o ``"FAIL <path>: <detalle>"`` (detalle es
      ``exit_code=N`` o el valor de ``error``). Devuelve 0 si TODOS los items
      de ``run_all`` tienen ``ok is True``, 1 si al menos uno es False, 1 si
      ``collect_contracts`` esta vacio (nada que validar es un error de
      configuracion, no un exito vacuo).

Todos los fixtures de contrato son tmp_path (no toca knowledge/contracts real
ni corre los test_command reales del repo: eso lo hace la ejecucion en CI,
este oraculo fija el comportamiento del gate en aislamiento).
"""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import validate_test_commands as vtc  # noqa: E402


def _write(path, content):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)


def _contract(test_command_line, name='sample.md'):
    return (
        "---\n"
        "type: 'Task Contract'\n"
        "title: 'x'\n"
        + test_command_line +
        "\n---\n\n# Contract\n"
    )


def _write_exit_script(directory, name, code):
    """Escribe un .py que solo hace ``sys.exit(code)``; evita comillas anidadas en YAML."""
    path = os.path.join(directory, name)
    _write(path, "import sys\nsys.exit({})\n".format(code))
    return path


class TestExtractTestCommand(unittest.TestCase):
    def test_double_quoted(self):
        text = _contract('test_command: "python -m unittest tests/test_x.py"')
        self.assertEqual(
            vtc.extract_test_command(text),
            "python -m unittest tests/test_x.py",
        )

    def test_single_quoted(self):
        text = _contract("test_command: 'python -m unittest tests/test_x.py'")
        self.assertEqual(
            vtc.extract_test_command(text),
            "python -m unittest tests/test_x.py",
        )

    def test_missing_key(self):
        text = "---\ntype: 'Task Contract'\ntitle: 'x'\n---\n\n# Contract\n"
        self.assertIsNone(vtc.extract_test_command(text))

    def test_empty_value(self):
        text = _contract('test_command: ""')
        self.assertIsNone(vtc.extract_test_command(text))


class TestCollectContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_collects_and_sorts(self):
        _write(os.path.join(self.tmp, 'b.md'), _contract('test_command: "echo b"'))
        _write(os.path.join(self.tmp, 'a.md'), _contract('test_command: "echo a"'))
        result = vtc.collect_contracts(self.tmp)
        paths = [os.path.basename(item['path']) for item in result]
        self.assertEqual(paths, ['a.md', 'b.md'])
        self.assertEqual(result[0]['test_command'], 'echo a')

    def test_skips_template_prefix(self):
        _write(
            os.path.join(self.tmp, 'TEMPLATE-x.md'),
            _contract('test_command: "echo t"'),
        )
        _write(os.path.join(self.tmp, 'real.md'), _contract('test_command: "echo r"'))
        result = vtc.collect_contracts(self.tmp)
        self.assertEqual(len(result), 1)
        self.assertEqual(os.path.basename(result[0]['path']), 'real.md')

    def test_skips_missing_test_command(self):
        _write(
            os.path.join(self.tmp, 'no_cmd.md'),
            "---\ntype: 'Task Contract'\ntitle: 'x'\n---\n\n# Contract\n",
        )
        result = vtc.collect_contracts(self.tmp)
        self.assertEqual(result, [])

    def test_ignores_non_md_files(self):
        _write(os.path.join(self.tmp, 'notes.txt'), 'hello')
        result = vtc.collect_contracts(self.tmp)
        self.assertEqual(result, [])


class TestRunTestCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_success(self):
        script = _write_exit_script(self.tmp, 'exit0.py', 0)
        result = vtc.run_test_command(
            '{} {}'.format(sys.executable, script),
            cwd='.',
            timeout=10,
        )
        self.assertEqual(result, {'exit_code': 0, 'ok': True, 'error': None})

    def test_nonzero_exit(self):
        script = _write_exit_script(self.tmp, 'exit3.py', 3)
        result = vtc.run_test_command(
            '{} {}'.format(sys.executable, script),
            cwd='.',
            timeout=10,
        )
        self.assertEqual(result, {'exit_code': 3, 'ok': False, 'error': None})

    def test_timeout(self):
        sleep_script = os.path.join(self.tmp, 'sleep5.py')
        _write(sleep_script, "import time\ntime.sleep(5)\n")
        result = vtc.run_test_command(
            '{} {}'.format(sys.executable, sleep_script),
            cwd='.',
            timeout=1,
        )
        self.assertEqual(result['ok'], False)
        self.assertEqual(result['error'], 'timeout')
        self.assertIsNone(result['exit_code'])

    def test_command_not_found(self):
        result = vtc.run_test_command(
            'this-binary-does-not-exist-anywhere --flag',
            cwd='.',
            timeout=10,
        )
        self.assertEqual(result['ok'], False)
        self.assertEqual(result['error'], 'not_found')
        self.assertIsNone(result['exit_code'])


class TestRunAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mixed_pass_fail(self):
        ok_script = _write_exit_script(self.tmp, 'ok_script.py', 0)
        bad_script = _write_exit_script(self.tmp, 'bad_script.py', 1)
        _write(
            os.path.join(self.tmp, 'ok.md'),
            _contract('test_command: "{} {}"'.format(sys.executable, ok_script)),
        )
        _write(
            os.path.join(self.tmp, 'bad.md'),
            _contract('test_command: "{} {}"'.format(sys.executable, bad_script)),
        )
        result = vtc.run_all(self.tmp, repo_root='.', timeout=10)
        self.assertEqual(len(result), 2)
        by_name = {os.path.basename(item['path']): item for item in result}
        self.assertTrue(by_name['ok.md']['ok'])
        self.assertFalse(by_name['bad.md']['ok'])
        self.assertEqual(by_name['bad.md']['exit_code'], 1)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_pass_returns_0(self):
        ok_script = _write_exit_script(self.tmp, 'ok_script.py', 0)
        _write(
            os.path.join(self.tmp, 'ok.md'),
            _contract('test_command: "{} {}"'.format(sys.executable, ok_script)),
        )
        code = vtc.main(['prog', self.tmp, '.'])
        self.assertEqual(code, 0)

    def test_any_fail_returns_1(self):
        bad_script = _write_exit_script(self.tmp, 'bad_script.py', 1)
        _write(
            os.path.join(self.tmp, 'bad.md'),
            _contract('test_command: "{} {}"'.format(sys.executable, bad_script)),
        )
        code = vtc.main(['prog', self.tmp, '.'])
        self.assertEqual(code, 1)

    def test_empty_directory_returns_1(self):
        code = vtc.main(['prog', self.tmp, '.'])
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
