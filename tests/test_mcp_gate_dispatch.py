"""Oraculo congelado de la capa de despacho del MCP server (Contrato: mcp-gate-dispatch).

Fija el comportamiento de ``scripts/mcp_gate_dispatch.py``: la logica PURA
(sin el SDK ``mcp``, stdlib solamente) que sabe que script correr por cada
gate y como armar su ``argv``. El wiring MCP real (``scripts/mcp_server.py``)
importa este modulo y expone cada entrada como una tool -- separado a
proposito para que esta logica sea testeable sin el SDK ``mcp`` instalado.

  API:
    ``GATE_SPECS`` -- dict ``{tool_name: {'script','params','defaults'}}``.
      ``script`` es la ruta relativa al repo_root (ej. ``scripts/validate_contracts.py``).
      ``params`` es la lista ordenada de nombres de parametro posicionales
      que el script CLI espera. ``defaults`` es un dict ``{param: valor}``
      -- valores ``str`` para parametros simples, ``list[str]`` para
      parametros que se expanden a MULTIPLES argv (ej. ``dirs`` de
      ``scan_secrets``, ``dirs`` de ``validate_skills``).
    ``build_argv(tool_name, params) -> list[str]`` -- ``[sys.executable,
      '<repo>/scripts/<gate>.py', ...args]``. ``params`` (dict) puede omitir
      claves -- se usa el default de ``GATE_SPECS``. Un valor ``list``
      se expande a multiples argv (uno por elemento, EN ORDEN, sin unirlos
      con espacios -- subprocess.run recibe una lista, no pasa por shell).
      ``KeyError`` si ``tool_name`` no esta en ``GATE_SPECS``.
    ``run_gate(tool_name, params, repo_root='.', timeout=120) ->
      {'exit_code','stdout','stderr'}`` -- corre ``build_argv(...)`` via
      ``subprocess.run(cwd=repo_root, capture_output=True, text=True,
      timeout=timeout)``. Nunca lanza excepcion por un exit code !=0 (eso
      es informacion, no un error de la funcion); SI puede propagar
      ``subprocess.TimeoutExpired`` (dejar que el caller lo maneje) --
      NO, en realidad: la captura y la traduce a
      ``{'exit_code': None, 'stdout': '', 'stderr': 'timeout after Ns'}``.
    ``run_all_level1(repo_root='.') -> {'overall_ok': bool, 'results':
      {tool_name: {'exit_code','stdout','stderr'}}}`` -- corre, EN ESTE
      ORDEN, los 11 gates de Nivel 1 (todas las claves de ``GATE_SPECS``
      EXCEPTO ``validate_attestation``, que es local-only y no forma parte
      del pipeline de Nivel 1 -- ver knowledge/contracts/attestation-gate.md)
      con sus params default, contra ``repo_root``. ``overall_ok`` es
      ``True`` solo si TODOS los ``exit_code`` son ``0``.
    ``seal_tests(tests_path, repo_root='.') -> {'hash': str|None,
      'exit_code': int, 'stdout': str}`` -- corre
      ``python scripts/validate_contracts.py --hash <tests_path>`` y
      extrae el hash (linea de 64 chars hex) del stdout. ``hash`` es
      ``None`` si el exit code no fue 0 o no se encontro un hash valido
      en el stdout.
"""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import mcp_gate_dispatch as gd  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestGateSpecs(unittest.TestCase):
    def test_all_12_gates_present(self):
        expected = {
            'validate_contracts', 'validate_specs', 'validate_okf',
            'lint_ascii', 'validate_rules', 'validate_skills',
            'validate_changelog', 'validate_ux_page', 'validate_diagrams',
            'validate_test_commands', 'scan_secrets', 'validate_attestation',
        }
        self.assertEqual(set(gd.GATE_SPECS.keys()), expected)

    def test_every_spec_has_script_params_defaults(self):
        for name, spec in gd.GATE_SPECS.items():
            self.assertIn('script', spec, name)
            self.assertIn('params', spec, name)
            self.assertIn('defaults', spec, name)
            self.assertTrue(spec['script'].startswith('scripts/'), name)


class TestBuildArgv(unittest.TestCase):
    def test_simple_dir_param_uses_default(self):
        argv = gd.build_argv('validate_contracts', {})
        self.assertEqual(argv[0], sys.executable)
        self.assertTrue(argv[1].endswith('validate_contracts.py'))
        self.assertEqual(argv[2:], ['knowledge/contracts'])

    def test_simple_dir_param_override(self):
        argv = gd.build_argv('validate_contracts', {'dir': 'custom/dir'})
        self.assertEqual(argv[2:], ['custom/dir'])

    def test_no_params_gate(self):
        argv = gd.build_argv('validate_changelog', {})
        self.assertTrue(argv[1].endswith('validate_changelog.py'))
        self.assertEqual(argv[2:], [])

    def test_list_param_default_expands_to_multiple_argv(self):
        argv = gd.build_argv('validate_skills', {})
        self.assertEqual(argv[2:], ['skills', '.agents/skills'])

    def test_list_param_override_expands(self):
        argv = gd.build_argv('scan_secrets', {'dirs': ['a', 'b', 'c']})
        self.assertEqual(argv[2:], ['a', 'b', 'c'])

    def test_two_param_gate_order_preserved(self):
        argv = gd.build_argv('validate_test_commands', {})
        self.assertEqual(argv[2:], ['knowledge/contracts', '.'])

    def test_unknown_tool_raises_keyerror(self):
        with self.assertRaises(KeyError):
            gd.build_argv('not_a_real_gate', {})


class TestRunGate(unittest.TestCase):
    # 'lint_ascii' (no 'validate_contracts') a proposito: este oraculo corre
    # dentro de la suite del propio repo, que test_init_project.py a veces
    # ejecuta sobre una COPIA mutada donde ya borro tests/test_init_project.py
    # (su propia guarda anti-recursion) -- eso hace que validate_contracts
    # falle ahi porque init-project.md declara justo ese archivo en su campo
    # tests:. lint_ascii solo mira scripts/*.py, que esa mutacion no toca, asi
    # que el resultado es estable sin importar que copia del repo lo corra.
    def test_run_against_real_repo_ok(self):
        result = gd.run_gate('lint_ascii', {}, repo_root=REPO_ROOT)
        self.assertEqual(result['exit_code'], 0, result['stdout'] + result['stderr'])

    def test_run_with_bad_dir_nonzero_exit_no_exception(self):
        result = gd.run_gate(
            'validate_contracts', {'dir': 'does/not/exist'}, repo_root=REPO_ROOT)
        self.assertNotEqual(result['exit_code'], 0)

    def test_timeout_translates_cleanly(self):
        result = gd.run_gate(
            'validate_test_commands', {}, repo_root=REPO_ROOT, timeout=0.001)
        self.assertIsNone(result['exit_code'])
        self.assertIn('timeout', result['stderr'])

    def test_bad_repo_root_no_exception(self):
        # repo_root (cwd del subprocess) inexistente: "Nunca lanza" tambien
        # cubre el OSError del propio subprocess (NotADirectoryError/
        # FileNotFoundError), no solo el exit code del gate. AUDIT-05 H-2.
        result = gd.run_gate('lint_ascii', {},
                             repo_root='does-not-exist-kdd-xyz')
        self.assertIsNotNone(result['exit_code'])
        self.assertNotEqual(result['exit_code'], 0)
        self.assertNotEqual(result['stderr'], '')


class TestRunAllLevel1(unittest.TestCase):
    # NUNCA correr run_all_level1 contra REPO_ROOT (el repo real) en este
    # oraculo: run_all_level1 incluye validate_test_commands, que corre el
    # test_command de CADA contrato -- incluido init-project.md, cuyo test
    # (test_gates_verdes_post_apply_en_copia) copia el repo entero y vuelve a
    # correr `python -m unittest discover`, que a su vez incluye ESTE MISMO
    # archivo de test -- una llamada a run_all_level1(REPO_ROOT) explota
    # recursivamente (cada nivel de copia vuelve a disparar el mismo ciclo).
    # Todos los tests de esta clase usan un tmpdir aislado, nunca el repo real.
    def test_excludes_attestation_and_runs_rest(self):
        tmp = tempfile.mkdtemp()
        try:
            result = gd.run_all_level1(repo_root=tmp)
            self.assertNotIn('validate_attestation', result['results'])
            self.assertEqual(len(result['results']), 11)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_overall_ok_false_if_any_gate_fails(self):
        tmp = tempfile.mkdtemp()
        try:
            result = gd.run_all_level1(repo_root=tmp)
            self.assertFalse(result['overall_ok'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSealTests(unittest.TestCase):
    def test_seals_real_test_file(self):
        result = gd.seal_tests(
            'tests/test_mcp_gate_dispatch.py', repo_root=REPO_ROOT)
        self.assertEqual(result['exit_code'], 0)
        self.assertIsNotNone(result['hash'])
        self.assertEqual(len(result['hash']), 64)

    def test_nonexistent_file_no_hash(self):
        result = gd.seal_tests('tests/does_not_exist.py', repo_root=REPO_ROOT)
        self.assertIsNone(result['hash'])


if __name__ == '__main__':
    unittest.main()
