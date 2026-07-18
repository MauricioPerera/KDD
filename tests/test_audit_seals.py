"""Oraculo congelado del auditor de seals debiles (Contrato: seal-audit).

Fija el comportamiento de ``scripts/audit_seals.py`` contra fixtures en
tmpdir aislados (nunca el repo vivo). El auditor es ADVISORY: detecta
oraculos que el sello certifica como integros pero que no pueden fallar
(sin asserts reales, sin funciones de test, sin referenciar al target).
El sello garantiza integridad; este auditor reporta ausencia de fuerza.

  API que congela:
    Reglas (constantes str): WEAK_TESTS_MISSING, WEAK_TESTS_EMPTY,
      WEAK_TESTS_UNPARSEABLE, WEAK_NO_TEST_FUNCTIONS, WEAK_NO_ASSERTS,
      WEAK_TARGET_UNREFERENCED.
    ``audit_contract(contract_path, repo_root) -> list[dict]`` -- findings
      ``{'contract','rule','msg'}`` de UN contrato (lista vacia = sano).
    ``audit_seals(contracts_dir='knowledge/contracts', repo_root='.')
      -> {'findings': [...], 'checked': int}`` -- todos los contratos
      ``*.md`` del dir (salta ``TEMPLATE-*``), findings ordenados por
      (contract, rule).
    ``main(argv) -> int`` -- argv estilo sys.argv; flags ``--repo-root``,
      ``--strict``; posicional opcional contracts_dir. Sin ``--strict``
      SIEMPRE devuelve 0 (advisory); con ``--strict`` devuelve 1 si hay
      findings.

  Semantica congelada:
    - ``assert`` con test constante (``assert True``) NO cuenta como
      assert real; ``self.assert*`` y ``assertRaises`` si cuentan.
    - tests no-Python (p.ej. ``.js``): solo aplican MISSING/EMPTY/
      TARGET_UNREFERENCED (el analisis AST es Python-only).
    - ``target == tests`` (contratos de coherencia auto-referenciales):
      TARGET_UNREFERENCED se omite -- un archivo se cubre a si mismo.
    - MISSING/EMPTY/UNPARSEABLE cortocircuitan el resto de reglas del
      contrato.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'scripts'))

import audit_seals as mod

HEALTHY_PY = (
    'import unittest\n'
    'import mymodule\n\n'
    'class TestAlgo(unittest.TestCase):\n'
    '    def test_uno(self):\n'
    '        self.assertEqual(mymodule.f(1), 2)\n'
)


class _Base(unittest.TestCase):
    def make_repo(self):
        tmp = tempfile.mkdtemp(prefix='seal-audit-oracle-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, 'knowledge', 'contracts'))
        os.makedirs(os.path.join(tmp, 'tests'))
        return tmp

    def add_contract(self, tmp, name, target, tests, tests_src=None):
        lines = [
            '---',
            'task: %s' % name,
            'target: %s' % target,
            'tests: "%s"' % tests,
            'tests_sha256: "%s"' % ('0' * 64),
            'test_command: "python -m unittest %s"' % tests,
            '---',
            '',
            'cuerpo',
            '',
        ]
        path = os.path.join(tmp, 'knowledge', 'contracts', name + '.md')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write('\n'.join(lines))
        if tests_src is not None:
            tpath = os.path.join(tmp, tests)
            os.makedirs(os.path.dirname(tpath), exist_ok=True)
            with open(tpath, 'w', encoding='utf-8', newline='') as fh:
                fh.write(tests_src)
        return path

    def rules_of(self, findings):
        return sorted(f['rule'] for f in findings)


class TestContratoSano(_Base):
    def test_py_sano_cero_findings(self):
        tmp = self.make_repo()
        p = self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                              'tests/test_demo.py', HEALTHY_PY)
        self.assertEqual(mod.audit_contract(p, tmp), [])

    def test_autoreferencial_target_igual_tests_cero_findings(self):
        tmp = self.make_repo()
        src = ('import unittest\n'
               'class T(unittest.TestCase):\n'
               '    def test_coherencia(self):\n'
               '        self.assertTrue(len("x") == 1)\n')
        p = self.add_contract(tmp, 'coh', 'tests/test_coh.py',
                              'tests/test_coh.py', src)
        self.assertEqual(mod.audit_contract(p, tmp), [])

    def test_no_python_con_referencia_cero_findings(self):
        tmp = self.make_repo()
        src = "const t = require('node:test');\nrequire('./greet.js');\n"
        p = self.add_contract(tmp, 'njs', 'examples/greet.js',
                              'examples/greet.test.js', src)
        self.assertEqual(mod.audit_contract(p, tmp), [])


class TestDebilidades(_Base):
    def test_sin_asserts_reales(self):
        tmp = self.make_repo()
        src = ('import mymodule\n'
               'def test_nada():\n'
               '    assert True\n')
        p = self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                              'tests/test_demo.py', src)
        self.assertEqual(self.rules_of(mod.audit_contract(p, tmp)),
                         ['WEAK_NO_ASSERTS'])

    def test_sin_funciones_de_test(self):
        tmp = self.make_repo()
        src = ('import mymodule\n'
               'def helper():\n'
               '    assert mymodule.f() == 1\n')
        p = self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                              'tests/test_demo.py', src)
        self.assertEqual(self.rules_of(mod.audit_contract(p, tmp)),
                         ['WEAK_NO_TEST_FUNCTIONS'])

    def test_target_no_referenciado(self):
        tmp = self.make_repo()
        src = ('import unittest\n'
               'class T(unittest.TestCase):\n'
               '    def test_x(self):\n'
               '        self.assertEqual(1 + 1, 2)\n')
        p = self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                              'tests/test_demo.py', src)
        self.assertEqual(self.rules_of(mod.audit_contract(p, tmp)),
                         ['WEAK_TARGET_UNREFERENCED'])

    def test_no_python_sin_referencia(self):
        tmp = self.make_repo()
        src = "const assert = require('node:assert');\n"
        p = self.add_contract(tmp, 'njs', 'examples/greet.js',
                              'examples/greet.test.js', src)
        self.assertEqual(self.rules_of(mod.audit_contract(p, tmp)),
                         ['WEAK_TARGET_UNREFERENCED'])

    def test_tests_vacio_cortocircuita(self):
        tmp = self.make_repo()
        p = self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                              'tests/test_demo.py', '   \n')
        self.assertEqual(self.rules_of(mod.audit_contract(p, tmp)),
                         ['WEAK_TESTS_EMPTY'])

    def test_tests_faltante(self):
        tmp = self.make_repo()
        p = self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                              'tests/test_demo.py', None)
        self.assertEqual(self.rules_of(mod.audit_contract(p, tmp)),
                         ['WEAK_TESTS_MISSING'])

    def test_tests_py_con_syntax_error(self):
        tmp = self.make_repo()
        p = self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                              'tests/test_demo.py', 'def broken(:\n')
        self.assertEqual(self.rules_of(mod.audit_contract(p, tmp)),
                         ['WEAK_TESTS_UNPARSEABLE'])


class TestAuditSeals(_Base):
    def test_recorre_dir_salta_template_y_ordena(self):
        tmp = self.make_repo()
        self.add_contract(tmp, 'zeta', 'scripts/zmod.py',
                          'tests/test_zeta.py',
                          'import zmod\ndef test_a():\n    assert True\n')
        self.add_contract(tmp, 'alfa', 'scripts/amod.py',
                          'tests/test_alfa.py', HEALTHY_PY.replace(
                              'mymodule', 'amod'))
        self.add_contract(tmp, 'TEMPLATE-task-contract',
                          'scripts/x.py', 'tests/test_x.py', None)
        out = mod.audit_seals(
            contracts_dir=os.path.join(tmp, 'knowledge', 'contracts'),
            repo_root=tmp)
        self.assertEqual(out['checked'], 2)
        self.assertEqual([f['contract'] for f in out['findings']],
                         ['zeta.md'])
        self.assertEqual(out['findings'][0]['rule'], 'WEAK_NO_ASSERTS')

    def test_contrato_sin_frontmatter_se_salta_sin_crash(self):
        tmp = self.make_repo()
        path = os.path.join(tmp, 'knowledge', 'contracts', 'roto.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('sin frontmatter\n')
        out = mod.audit_seals(
            contracts_dir=os.path.join(tmp, 'knowledge', 'contracts'),
            repo_root=tmp)
        self.assertEqual(out['checked'], 0)
        self.assertEqual(out['findings'], [])


class TestMain(_Base):
    def _repo_con_finding(self):
        tmp = self.make_repo()
        self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                          'tests/test_demo.py',
                          'import mymodule\ndef test_a():\n    assert True\n')
        return tmp

    def _argv(self, tmp, *extra):
        return (['audit_seals',
                 os.path.join(tmp, 'knowledge', 'contracts'),
                 '--repo-root', tmp] + list(extra))

    def test_advisory_devuelve_0_con_findings(self):
        tmp = self._repo_con_finding()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = mod.main(self._argv(tmp))
        self.assertEqual(rc, 0)
        self.assertIn('WEAK_NO_ASSERTS', buf.getvalue())

    def test_strict_devuelve_1_con_findings(self):
        tmp = self._repo_con_finding()
        with contextlib.redirect_stdout(io.StringIO()):
            rc = mod.main(self._argv(tmp, '--strict'))
        self.assertEqual(rc, 1)

    def test_strict_devuelve_0_limpio(self):
        tmp = self.make_repo()
        self.add_contract(tmp, 'demo', 'scripts/mymodule.py',
                          'tests/test_demo.py', HEALTHY_PY)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = mod.main(self._argv(tmp, '--strict'))
        self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
