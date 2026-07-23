"""Oraculo congelado del preflight (Contrato: preflight).

Fija el comportamiento de ``scripts/preflight.py`` SIN correr jamas los
gates reales: el modo full se prueba con un runner fake inyectado (nunca
``run_all_level1`` contra el repo vivo -- ver la advertencia de recursion
en ``knowledge/mcp-server.md``) y el modo ``--contract`` se prueba contra
fixtures en un tmpdir aislado.

  API que congela:
    ``ALL_GATES`` -- ``LEVEL1_GATES`` + ``['validate_attestation']`` (12).
    ``run_preflight(repo_root='.', contract=None, runner=None) -> dict``
      modo full (contract None): corre los 12 gates via ``runner``
      (default: la referencia de modulo ``preflight.run_gate``) con
      ``params={}`` y el ``repo_root`` dado. Devuelve ``{'mode': 'full',
      'overall_ok': bool, 'results': {gate: {'exit_code','stdout','stderr'}},
      'lines': [str]}`` -- una linea por gate (nombre + PASS/FAIL/TIMEOUT)
      y una linea resumen con ``<pasados>/<total>``.
      modo contract: NO corre los 12 gates; corre 3 chequeos sobre
      ``knowledge/contracts/<contract>.md`` -- ``frontmatter`` (existe y
      declara tests/tests_sha256/test_command), ``seal`` (sha256 del
      archivo de tests, LF-normalizado, igual a ``tests_sha256``) y
      ``test_command`` (subprocess con cwd=repo_root; su exit code).
    ``main(argv) -> int`` -- argv estilo sys.argv; flags ``--repo-root DIR``
      y ``--contract NAME``. Imprime las lineas y devuelve 0 si
      ``overall_ok`` es True, 1 si no.
"""
import contextlib
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'scripts'))

import mcp_gate_dispatch
import preflight

EXPECTED_GATES = list(mcp_gate_dispatch.LEVEL1_GATES) + ['validate_attestation']


def _ok_runner(name, params, repo_root='.', timeout=120):
    return {'exit_code': 0, 'stdout': 'ok', 'stderr': ''}


def _sha256_lf(text):
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


class TestAllGatesConstant(unittest.TestCase):
    def test_all_gates_es_level1_mas_attestation(self):
        self.assertEqual(list(preflight.ALL_GATES), EXPECTED_GATES)
        self.assertEqual(len(preflight.ALL_GATES), 12)


class TestFullMode(unittest.TestCase):
    def test_todos_pasan(self):
        calls = []

        def runner(name, params, repo_root='.', timeout=120):
            calls.append((name, params, repo_root))
            return {'exit_code': 0, 'stdout': '', 'stderr': ''}

        res = preflight.run_preflight(repo_root='algun-root', runner=runner)
        self.assertEqual(res['mode'], 'full')
        self.assertTrue(res['overall_ok'])
        self.assertEqual(list(res['results'].keys()), EXPECTED_GATES)
        self.assertEqual([c[0] for c in calls], EXPECTED_GATES)
        for _name, params, root in calls:
            self.assertEqual(params, {})
            self.assertEqual(root, 'algun-root')

    def test_lineas_y_resumen_todos_pasan(self):
        res = preflight.run_preflight(runner=_ok_runner)
        lines = res['lines']
        for name in EXPECTED_GATES:
            self.assertTrue(
                any(name in ln and 'PASS' in ln for ln in lines),
                'falta linea PASS para %s' % name)
        self.assertTrue(any('12/12' in ln for ln in lines),
                        'falta resumen 12/12')

    def test_un_gate_falla(self):
        def runner(name, params, repo_root='.', timeout=120):
            if name == 'validate_okf':
                return {'exit_code': 2, 'stdout': '', 'stderr': 'boom'}
            return {'exit_code': 0, 'stdout': '', 'stderr': ''}

        res = preflight.run_preflight(runner=runner)
        self.assertFalse(res['overall_ok'])
        self.assertEqual(res['results']['validate_okf']['exit_code'], 2)
        lines = res['lines']
        self.assertTrue(
            any('validate_okf' in ln and 'FAIL' in ln for ln in lines))
        self.assertTrue(any('11/12' in ln for ln in lines))

    def test_timeout_se_reporta_como_timeout(self):
        def runner(name, params, repo_root='.', timeout=120):
            if name == 'scan_secrets':
                return {'exit_code': None, 'stdout': '',
                        'stderr': 'timeout after 120s'}
            return {'exit_code': 0, 'stdout': '', 'stderr': ''}

        res = preflight.run_preflight(runner=runner)
        self.assertFalse(res['overall_ok'])
        lines = res['lines']
        self.assertTrue(
            any('scan_secrets' in ln and 'TIMEOUT' in ln for ln in lines))
        self.assertTrue(any('11/12' in ln for ln in lines))

    def test_main_todo_verde_devuelve_0(self):
        with mock.patch.object(preflight, 'run_gate', new=_ok_runner):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = preflight.main(['preflight'])
        self.assertEqual(rc, 0)

    def test_main_con_fallo_devuelve_1(self):
        def runner(name, params, repo_root='.', timeout=120):
            code = 1 if name == 'lint_ascii' else 0
            return {'exit_code': code, 'stdout': '', 'stderr': ''}

        with mock.patch.object(preflight, 'run_gate', new=runner):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = preflight.main(['preflight'])
        self.assertEqual(rc, 1)


class TestContractMode(unittest.TestCase):
    CHECKS = ['frontmatter', 'seal', 'test_command']

    def _make_repo(self, newline='\n', seal=None,
                   test_command='python exit0.py', with_contract=True):
        tmp = tempfile.mkdtemp(prefix='preflight-oracle-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, 'knowledge', 'contracts'))
        os.makedirs(os.path.join(tmp, 'tests'))
        tests_txt = 'X = 1\n'
        with open(os.path.join(tmp, 'tests', 'test_dummy.py'), 'w',
                  encoding='utf-8', newline='') as fh:
            fh.write(tests_txt)
        with open(os.path.join(tmp, 'exit0.py'), 'w',
                  encoding='utf-8') as fh:
            fh.write('raise SystemExit(0)\n')
        with open(os.path.join(tmp, 'exit3.py'), 'w',
                  encoding='utf-8') as fh:
            fh.write('raise SystemExit(3)\n')
        if seal is None:
            seal = _sha256_lf(tests_txt)
        if with_contract:
            lines = [
                '---',
                'task: demo-task',
                'tests: "tests/test_dummy.py"',
                'tests_sha256: "%s"' % seal,
                'test_command: "%s"' % test_command,
                '---',
                '',
                'cuerpo',
                '',
            ]
            path = os.path.join(tmp, 'knowledge', 'contracts',
                                'demo-task.md')
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(newline.join(lines))
        return tmp

    def test_contrato_sano_pasa_3_de_3(self):
        tmp = self._make_repo()
        res = preflight.run_preflight(repo_root=tmp, contract='demo-task')
        self.assertEqual(res['mode'], 'contract')
        self.assertTrue(res['overall_ok'])
        self.assertEqual(list(res['results'].keys()), self.CHECKS)
        for check in self.CHECKS:
            self.assertEqual(res['results'][check]['exit_code'], 0, check)
        self.assertTrue(any('3/3' in ln for ln in res['lines']))

    def test_contrato_crlf_parsea_igual(self):
        tmp = self._make_repo(newline='\r\n')
        res = preflight.run_preflight(repo_root=tmp, contract='demo-task')
        self.assertTrue(res['overall_ok'])

    def test_seal_desincronizado_falla(self):
        tmp = self._make_repo(seal='0' * 64)
        res = preflight.run_preflight(repo_root=tmp, contract='demo-task')
        self.assertFalse(res['overall_ok'])
        self.assertEqual(res['results']['frontmatter']['exit_code'], 0)
        self.assertNotEqual(res['results']['seal']['exit_code'], 0)
        self.assertTrue(
            any('seal' in ln and 'FAIL' in ln for ln in res['lines']))

    def test_test_command_propaga_exit_code(self):
        tmp = self._make_repo(test_command='python exit3.py')
        res = preflight.run_preflight(repo_root=tmp, contract='demo-task')
        self.assertFalse(res['overall_ok'])
        self.assertEqual(res['results']['test_command']['exit_code'], 3)

    def test_contrato_inexistente_falla_en_frontmatter(self):
        tmp = self._make_repo(with_contract=False)
        res = preflight.run_preflight(repo_root=tmp, contract='demo-task')
        self.assertFalse(res['overall_ok'])
        self.assertNotEqual(res['results']['frontmatter']['exit_code'], 0)

    def test_modo_contract_no_corre_los_12_gates(self):
        tmp = self._make_repo()

        def boom(name, params, repo_root='.', timeout=120):
            raise AssertionError('el modo contract no debe correr gates')

        res = preflight.run_preflight(repo_root=tmp, contract='demo-task',
                                      runner=boom)
        self.assertTrue(res['overall_ok'])

    def test_main_modo_contract(self):
        tmp = self._make_repo()
        with contextlib.redirect_stdout(io.StringIO()):
            rc = preflight.main(['preflight', '--repo-root', tmp,
                                 '--contract', 'demo-task'])
        self.assertEqual(rc, 0)


class TestRobustez(unittest.TestCase):
    """Casos de robustez agregados tras AUDIT-05 (H-1, H-2, H-4)."""

    def _make_repo(self, tests_bytes):
        tmp = tempfile.mkdtemp(prefix='preflight-robustez-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, 'knowledge', 'contracts'))
        os.makedirs(os.path.join(tmp, 'tests'))
        with open(os.path.join(tmp, 'tests', 'test_dummy.py'), 'wb') as fh:
            fh.write(tests_bytes)
        with open(os.path.join(tmp, 'exit0.py'), 'w', encoding='utf-8') as fh:
            fh.write('raise SystemExit(0)\n')
        lines = [
            '---',
            'task: demo-task',
            'tests: "tests/test_dummy.py"',
            'tests_sha256: "%s"' % ('0' * 64),
            'test_command: "python exit0.py"',
            '---',
            '',
            'cuerpo',
            '',
        ]
        path = os.path.join(tmp, 'knowledge', 'contracts', 'demo-task.md')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write('\n'.join(lines))
        return tmp

    def test_tests_no_utf8_falla_seal_sin_lanzar(self):
        # H-1: un tests file no decodificable como utf-8 es un FAIL del
        # chequeo seal (informacion), jamas un traceback.
        tmp = self._make_repo(b'\xff\xfeBAD')
        res = preflight.run_preflight(repo_root=tmp, contract='demo-task')
        self.assertFalse(res['overall_ok'])
        self.assertEqual(res['results']['frontmatter']['exit_code'], 0)
        self.assertNotEqual(res['results']['seal']['exit_code'], 0)

    def test_main_repo_root_inexistente_devuelve_1_sin_lanzar(self):
        # H-2: modo full contra un repo_root inexistente reporta FAIL en
        # los gates y main devuelve 1 -- sin NotADirectoryError.
        with contextlib.redirect_stdout(io.StringIO()):
            rc = preflight.main(['preflight', '--repo-root',
                                 'does-not-exist-kdd-xyz'])
        self.assertEqual(rc, 1)

    def test_flags_forma_igual_aceptadas(self):
        # H-4: --contract=NAME y --repo-root=DIR (forma con '=') valen
        # igual que la forma con espacio; rc 0 prueba que corrio el modo
        # contract (el modo full sobre esta fixture daria 1).
        tmp = self._make_repo(b'X = 1\n')
        seal = hashlib.sha256(b'X = 1\n').hexdigest()
        cpath = os.path.join(tmp, 'knowledge', 'contracts', 'demo-task.md')
        with open(cpath, 'r', encoding='utf-8') as fh:
            body = fh.read()
        with open(cpath, 'w', encoding='utf-8', newline='') as fh:
            fh.write(body.replace('0' * 64, seal))
        with contextlib.redirect_stdout(io.StringIO()):
            rc = preflight.main(['preflight', '--repo-root=' + tmp,
                                 '--contract=demo-task'])
        self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
