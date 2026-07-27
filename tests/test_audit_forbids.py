"""Oraculo congelado del auditor de forbids (Contrato: forbids-audit).

Fija el comportamiento de ``scripts/audit_forbids.py``: auditor ADVISORY que
compara el ``forbids`` DECLARADO en un task contract contra lo que realmente
esta impedido. Hoy tiene dos verificadores, ambos para ``unsafe`` -- Rust y
Go -- y son deliberadamente distintos. Rust es el unico donde la prohibicion
es comprobable de verdad: rustc la impone sobre el crate entero. Go NO tiene
mecanismo de compilador equivalente, asi que su verificador solo comprueba
PRESENCIA del import (``go_denies_unsafe`` es siempre False). Las capacidades
sin verificador se reportan como ``FORBID_UNVERIFIED``, NO como sanas: la
diferencia entre "verificado" y "no verificable" es justo lo que este
auditor existe para hacer explicita.

  API:
    Reglas: ``FORBID_UNVERIFIED``, ``FORBID_UNSAFE_PRESENT``,
      ``FORBID_UNSAFE_UNENFORCED``.
    ``strip_noise(src) -> str`` -- fuente Rust sin comentarios de linea/bloque
      ni literales string.
    ``has_unsafe(src) -> bool`` -- True si USA la keyword ``unsafe`` fuera de
      comentarios/strings. ``unsafe_code`` NO cuenta (el guion bajo es
      caracter de palabra, asi que ``\\bunsafe\\b`` no matchea).
    ``crate_denies_unsafe(target, repo_root) -> bool`` -- True si el crate del
      target deniega unsafe a nivel compilador por CUALQUIERA de tres vias:
      atributo ``#![forbid|deny(unsafe_code)]`` en la raiz del crate,
      ``unsafe_code = "deny"|"forbid"`` bajo ``[lints.rust]`` del Cargo.toml
      propio, o herencia del workspace (``[lints] workspace = true`` +
      ``[workspace.lints.rust]`` en la raiz).
    ``audit_contract(path, repo_root) -> [{'contract','rule','msg'}]``
    ``audit_forbids(contracts_dir, repo_root) -> {'findings', 'checked'}`` --
      salta ``TEMPLATE-*``; findings ordenados por (contract, rule, msg).
    ``main(argv) -> int`` -- sin ``--strict`` SIEMPRE 0 (advisory); con
      ``--strict`` 1 solo si hay reglas DURAS (``FORBID_UNSAFE_PRESENT``);
      ``FORBID_UNVERIFIED`` nunca cambia el exit code (es una limitacion del
      auditor, no un incumplimiento del contrato).

Todos los fixtures son tmpdir: el oraculo no depende de este repo.
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import audit_forbids as af  # noqa: E402


CONTRACT = """---
type: 'Task Contract'
title: 'Demo'
task: demo
intent: "Demostrar."
language: rust
target: src/lib.rs
signature: "fn demo(a: i32) -> i32"
test_command: "cargo test"
budget:
  cyclomatic_max: 5
  nesting_max: 2
tests: "tests/demo.rs"
tests_sha256: "0000000000000000000000000000000000000000000000000000000000000000"
touch_only: ['src/lib.rs']
deps_allowed: []
forbids: ['unsafe']
---

## Intent
x

## Interface
fn demo(a: i32) -> i32

## Invariants
- x

## Examples
- demo(1) -> 1
- demo(2) -> 2

## Do / Don't
- DO: x

## Tests
tests/demo.rs

## Constraints
- PARAR y reportar si x.
"""


def _write(root, rel, content):
    p = os.path.join(root, rel)
    parent = os.path.dirname(p)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write(content)
    return p


class Fixture(unittest.TestCase):
    """Proyecto Rust minimo en tmpdir, parametrizable por caso."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, contract=CONTRACT, cargo='[package]\nname = "demo"\n',
               lib='pub fn demo(a: i32) -> i32 { a }\n', ws_cargo=None,
               crate_subdir=''):
        """Escribe el proyecto. Con `crate_subdir` el crate vive en un
        subdirectorio (layout de workspace) y `ws_cargo` es la raiz."""
        base = os.path.join(self.tmp, crate_subdir) if crate_subdir else self.tmp
        _write(base, 'Cargo.toml', cargo)
        _write(base, 'src/lib.rs', lib)
        if ws_cargo is not None:
            _write(self.tmp, 'Cargo.toml', ws_cargo)
        target = (crate_subdir + '/src/lib.rs') if crate_subdir else 'src/lib.rs'
        _write(self.tmp, 'knowledge/contracts/demo.md',
               contract.replace('target: src/lib.rs', 'target: ' + target)
                       .replace("touch_only: ['src/lib.rs']",
                                "touch_only: ['%s']" % target))
        return os.path.join(self.tmp, 'knowledge', 'contracts')

    def _rules(self, contracts_dir):
        res = af.audit_forbids(contracts_dir, self.tmp)
        return {f['rule'] for f in res['findings']}


class StripNoise(unittest.TestCase):
    def test_quita_comentario_de_linea(self):
        self.assertFalse(af.has_unsafe('// unsafe { }\nfn f() {}\n'))

    def test_quita_comentario_de_bloque(self):
        self.assertFalse(af.has_unsafe('/* unsafe\n   unsafe */\nfn f() {}\n'))

    def test_quita_literal_string(self):
        self.assertFalse(af.has_unsafe('let s = "unsafe";\n'))

    def test_detecta_uso_real(self):
        self.assertTrue(af.has_unsafe('fn f() { unsafe { g() } }\n'))

    def test_unsafe_code_no_es_uso(self):
        # 'unsafe_code' no debe contar: es el nombre del lint, no la keyword.
        self.assertFalse(af.has_unsafe('#![forbid(unsafe_code)]\nfn f() {}\n'))

    def test_identificador_que_empieza_con_unsafe_no_cuenta(self):
        self.assertFalse(af.has_unsafe('let unsafely = 1;\nfn unsafe_helper() {}\n'))

    def test_unsafe_fn_cuenta(self):
        self.assertTrue(af.has_unsafe('pub unsafe fn f() {}\n'))


class CrateDeniesUnsafe(Fixture):
    def test_atributo_en_raiz_del_crate(self):
        d = self._build(lib='#![forbid(unsafe_code)]\npub fn demo(a: i32) -> i32 { a }\n')
        self.assertTrue(af.crate_denies_unsafe('src/lib.rs', self.tmp))
        self.assertEqual(self._rules(d), set())

    def test_atributo_deny_tambien_vale(self):
        self._build(lib='#![deny(unsafe_code)]\npub fn demo(a: i32) -> i32 { a }\n')
        self.assertTrue(af.crate_denies_unsafe('src/lib.rs', self.tmp))

    def test_lints_del_cargo_toml_propio(self):
        d = self._build(cargo='[package]\nname = "demo"\n\n'
                              '[lints.rust]\nunsafe_code = "deny"\n')
        self.assertTrue(af.crate_denies_unsafe('src/lib.rs', self.tmp))
        self.assertEqual(self._rules(d), set())

    def test_lints_forma_tabla_con_level(self):
        self._build(cargo='[package]\nname = "demo"\n\n'
                          '[lints.rust]\nunsafe_code = { level = "forbid", priority = 0 }\n')
        self.assertTrue(af.crate_denies_unsafe('src/lib.rs', self.tmp))

    def test_heredado_del_workspace(self):
        d = self._build(
            cargo='[package]\nname = "demo"\n\n[lints]\nworkspace = true\n',
            ws_cargo='[workspace]\nmembers = ["crates/demo"]\n\n'
                     '[workspace.lints.rust]\nunsafe_code = "deny"\n',
            crate_subdir='crates/demo')
        self.assertTrue(af.crate_denies_unsafe('crates/demo/src/lib.rs', self.tmp))
        self.assertEqual(self._rules(d), set())

    def test_workspace_sin_denegacion_no_alcanza(self):
        self._build(
            cargo='[package]\nname = "demo"\n\n[lints]\nworkspace = true\n',
            ws_cargo='[workspace]\nmembers = ["crates/demo"]\n',
            crate_subdir='crates/demo')
        self.assertFalse(af.crate_denies_unsafe('crates/demo/src/lib.rs', self.tmp))

    def test_hereda_pero_no_declara_workspace_true(self):
        # Sin '[lints] workspace = true' el crate NO hereda: la denegacion de
        # la raiz no aplica.
        self._build(
            cargo='[package]\nname = "demo"\n',
            ws_cargo='[workspace]\n\n[workspace.lints.rust]\nunsafe_code = "deny"\n',
            crate_subdir='crates/demo')
        self.assertFalse(af.crate_denies_unsafe('crates/demo/src/lib.rs', self.tmp))

    def test_sin_cargo_toml_no_hay_denegacion(self):
        self.assertFalse(af.crate_denies_unsafe('src/lib.rs', self.tmp))

    def test_allow_no_es_denegacion(self):
        self._build(cargo='[package]\nname = "demo"\n\n'
                          '[lints.rust]\nunsafe_code = "allow"\n')
        self.assertFalse(af.crate_denies_unsafe('src/lib.rs', self.tmp))


class AuditFindings(Fixture):
    def test_declarado_sin_denegacion_y_sin_uso_es_warning(self):
        d = self._build()
        self.assertEqual(self._rules(d), {af.FORBID_UNSAFE_UNENFORCED})

    def test_declarado_sin_denegacion_con_uso_es_error_duro(self):
        d = self._build(lib='pub fn demo(a: i32) -> i32 { unsafe { a } }\n')
        self.assertEqual(self._rules(d), {af.FORBID_UNSAFE_PRESENT})

    def test_con_denegacion_y_uso_no_reporta(self):
        # El crate deniega: rustc rechaza la compilacion, la prohibicion del
        # contrato SI esta impuesta. El fallo de build es el enforcement.
        d = self._build(cargo='[package]\nname = "demo"\n\n'
                              '[lints.rust]\nunsafe_code = "deny"\n',
                        lib='pub fn demo(a: i32) -> i32 { unsafe { a } }\n')
        self.assertEqual(self._rules(d), set())

    def test_capacidad_sin_verificador_es_unverified(self):
        d = self._build(contract=CONTRACT.replace("forbids: ['unsafe']",
                                                  "forbids: ['network']"))
        self.assertEqual(self._rules(d), {af.FORBID_UNVERIFIED})

    def test_unsafe_en_lenguaje_sin_verificador_es_unverified(self):
        # forbids: unsafe sobre un target Python: no hay verificador para ese par.
        d = self._build(contract=CONTRACT.replace('language: rust', 'language: python'))
        self.assertEqual(self._rules(d), {af.FORBID_UNVERIFIED})

    def test_forbids_vacio_no_reporta(self):
        d = self._build(contract=CONTRACT.replace("forbids: ['unsafe']", 'forbids: []'))
        self.assertEqual(self._rules(d), set())

    def test_sin_forbids_no_reporta(self):
        d = self._build(contract=CONTRACT.replace("forbids: ['unsafe']\n", ''))
        self.assertEqual(self._rules(d), set())

    def test_template_se_salta(self):
        d = self._build()
        shutil.copy(os.path.join(d, 'demo.md'),
                    os.path.join(d, 'TEMPLATE-task-contract.md'))
        self.assertEqual(af.audit_forbids(d, self.tmp)['checked'], 1)

    def test_findings_ordenados(self):
        d = self._build(contract=CONTRACT.replace(
            "forbids: ['unsafe']", "forbids: ['unsafe', 'network', 'llm']"))
        findings = af.audit_forbids(d, self.tmp)['findings']
        self.assertEqual(findings, sorted(
            findings, key=lambda f: (f['contract'], f['rule'], f['msg'])))

    def test_contracts_dir_inexistente_no_lanza(self):
        res = af.audit_forbids(os.path.join(self.tmp, 'nope'), self.tmp)
        self.assertEqual(res, {'findings': [], 'checked': 0})


class MainCli(Fixture):
    def test_sin_strict_siempre_exit0(self):
        d = self._build(lib='pub fn demo(a: i32) -> i32 { unsafe { a } }\n')
        code = af.main(['audit_forbids.py', d, '--repo-root', self.tmp])
        self.assertEqual(code, 0)

    def test_strict_exit1_con_regla_dura(self):
        d = self._build(lib='pub fn demo(a: i32) -> i32 { unsafe { a } }\n')
        code = af.main(['audit_forbids.py', d, '--repo-root', self.tmp, '--strict'])
        self.assertEqual(code, 1)

    def test_strict_exit0_si_solo_hay_unverified(self):
        # FORBID_UNVERIFIED es una limitacion del auditor, no un incumplimiento:
        # no debe romper el build de nadie ni con --strict.
        d = self._build(contract=CONTRACT.replace("forbids: ['unsafe']",
                                                  "forbids: ['network']"))
        code = af.main(['audit_forbids.py', d, '--repo-root', self.tmp, '--strict'])
        self.assertEqual(code, 0)

    def test_strict_exit0_con_warning_de_unenforced(self):
        # UNENFORCED avisa que falta la garantia fuerte, pero hoy nada la viola.
        d = self._build()
        code = af.main(['audit_forbids.py', d, '--repo-root', self.tmp, '--strict'])
        self.assertEqual(code, 0)

    def test_repo_root_con_igual(self):
        d = self._build()
        code = af.main(['audit_forbids.py', d, '--repo-root=' + self.tmp])
        self.assertEqual(code, 0)


GO_CONTRACT = """---
type: 'Task Contract'
title: 'Demo Go'
task: demo
intent: "Demostrar."
language: go
target: main.go
signature: "func Demo(a int) int"
test_command: "go test"
budget:
  cyclomatic_max: 5
  nesting_max: 2
tests: "main_test.go"
tests_sha256: "0000000000000000000000000000000000000000000000000000000000000000"
touch_only: ['main.go']
deps_allowed: []
forbids: ['unsafe']
---

## Intent
x

## Interface
func Demo(a int) int

## Invariants
- x

## Examples
- Demo(1) -> 1

## Do / Don't
- DO: x

## Tests
main_test.go

## Constraints
- PARAR y reportar si x.
"""


class GoFixture(unittest.TestCase):
    """Proyecto Go minimo en tmpdir, parametrizable por caso.

    A diferencia de ``Fixture`` (Rust), no escribe ``Cargo.toml`` ni ``go.mod``:
    ``go_denies_unsafe`` es siempre False (Go no tiene mecanismo de compilador
    para prohibir el paquete unsafe), asi que el manifiesto es irrelevante para
    el auditor. Solo hacen falta el target ``.go`` y el contrato.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_go(self, contract=GO_CONTRACT,
                  gofile='package main\n\n'
                         'func Demo(a int) int { return a }\n'):
        _write(self.tmp, 'main.go', gofile)
        _write(self.tmp, 'knowledge/contracts/demo.md', contract)
        return os.path.join(self.tmp, 'knowledge', 'contracts')

    def _rules(self, contracts_dir):
        res = af.audit_forbids(contracts_dir, self.tmp)
        return {f['rule'] for f in res['findings']}


class GoHasUnsafeImport(unittest.TestCase):
    """Deteccion del import del paquete unsafe, anclada al import."""

    def test_comentario_de_linea_no_cuenta(self):
        self.assertFalse(af.go_has_unsafe_import(
            '// import "unsafe"\npackage main\n'))

    def test_comentario_de_bloque_no_cuenta(self):
        self.assertFalse(af.go_has_unsafe_import(
            '/* import "unsafe" */\npackage main\n'))

    def test_string_normal_no_cuenta(self):
        # Un string con comillas dobles que contiene "unsafe" no es un import:
        # la deteccion se ancla a ^import, no a cualquier aparicion de la
        # palabra. go_strip_noise NO quita los strings con comillas dobles
        # (la ruta del import es uno), pero como no empiezan con `import`, no
        # matchean.
        self.assertFalse(af.go_has_unsafe_import(
            'package main\nvar s = "unsafe"\n'))

    def test_string_normal_con_palabra_import_no_cuenta(self):
        # Incluso un string que literalmente dice `import "unsafe"` no cuenta:
        # la linea empieza con `var`, no con `import`.
        self.assertFalse(af.go_has_unsafe_import(
            'package main\nvar s = "import \\"unsafe\\""\n'))

    def test_raw_string_no_cuenta(self):
        # Un raw string (backtick) puede spansar lineas y fingir un import;
        # go_strip_noise lo quita. Sin el stripping, la linea `import
        # "unsafe"` dentro del raw contaria falsamente.
        self.assertFalse(af.go_has_unsafe_import(
            'package main\nvar s = `\nimport "unsafe"\n`\n'))

    def test_import_linea_unica_cuenta(self):
        self.assertTrue(af.go_has_unsafe_import(
            'package main\nimport "unsafe"\n'))

    def test_import_agrupado_cuenta(self):
        self.assertTrue(af.go_has_unsafe_import(
            'package main\nimport (\n\t"fmt"\n\t"unsafe"\n)\n'))

    def test_import_aliasado_cuenta(self):
        self.assertTrue(af.go_has_unsafe_import(
            'package main\nimport u "unsafe"\n'))

    def test_import_blank_cuenta(self):
        self.assertTrue(af.go_has_unsafe_import(
            'package main\nimport _ "unsafe"\n'))

    def test_import_dot_cuenta(self):
        self.assertTrue(af.go_has_unsafe_import(
            'package main\nimport . "unsafe"\n'))

    def test_import_agrupado_aliasado_cuenta(self):
        self.assertTrue(af.go_has_unsafe_import(
            'package main\nimport (\n\tu "unsafe"\n)\n'))

    def test_identificador_no_es_import(self):
        # `isUnsafe` / `unsafePool` son identificadores, no el import del
        # paquete: un `\bunsafe\b` sobre todo el archivo daria falso positivo
        # aqui. La deteccion anclada al import no los cuenta.
        self.assertFalse(af.go_has_unsafe_import(
            'package main\nvar isUnsafe = 1\nvar unsafePool = 2\n'))

    def test_import_otro_paquete_no_cuenta(self):
        self.assertFalse(af.go_has_unsafe_import(
            'package main\nimport "fmt"\n'))

    def test_import_agrupado_sin_unsafe_no_cuenta(self):
        self.assertFalse(af.go_has_unsafe_import(
            'package main\nimport (\n\t"fmt"\n\t"os"\n)\n'))


class GoDeniesUnsafe(GoFixture):
    def test_siempre_false_go_no_tiene_mecanismo(self):
        # Go NO tiene mecanismo de compilador para prohibir el paquete unsafe a
        # nivel proyecto (no hay flag de build, ni lint estandar, ni convencion
        # en go.mod, a diferencia de Rust). go_denies_unsafe devuelve False
        # siempre, por diseno: es la honestidad de la ausencia de enforcement,
        # no un bug pendiente. Si algun dia se integra un analizador estatico
        # custom (go/analysis) que verifique la denegacion, esta funcion es
        # donde anzadirlo -- mientras tanto, devuelve False.
        self._build_go()
        self.assertFalse(af.go_denies_unsafe('main.go', self.tmp))


class GoAuditFindings(GoFixture):
    def test_declarado_sin_import_es_warning_unenforced(self):
        d = self._build_go()
        self.assertEqual(self._rules(d), {af.FORBID_UNSAFE_UNENFORCED})

    def test_declarado_con_import_es_error_duro(self):
        d = self._build_go(gofile='package main\nimport "unsafe"\n\n'
                                   'func Demo(a int) int { return a }\n')
        self.assertEqual(self._rules(d), {af.FORBID_UNSAFE_PRESENT})

    def test_declarado_con_import_agrupado_es_error_duro(self):
        d = self._build_go(gofile='package main\nimport (\n\t"unsafe"\n)\n\n'
                                   'func Demo(a int) int { return a }\n')
        self.assertEqual(self._rules(d), {af.FORBID_UNSAFE_PRESENT})

    def test_go_no_tiene_denegacion_que_silencie_el_uso(self):
        # A diferencia de Rust (donde denegar a nivel crate silencia el
        # reporta), en Go no hay denegacion posible: un target que importa
        # unsafe SIEMPRE es FORBID_UNSAFE_PRESENT, nunca [].
        d = self._build_go(gofile='package main\nimport "unsafe"\n\n'
                                   'func Demo(a int) int { return a }\n')
        self.assertEqual(self._rules(d), {af.FORBID_UNSAFE_PRESENT})

    def test_unsafe_en_lenguaje_sin_verificador_sigue_unverified(self):
        # El verificador Go no rompe el comportamiento default: un lenguaje
        # sin verificador para (unsafe, lang) sigue dando FORBID_UNVERIFIED.
        d = self._build_go(contract=GO_CONTRACT.replace('language: go',
                                                        'language: python'))
        self.assertEqual(self._rules(d), {af.FORBID_UNVERIFIED})

    def test_forbids_vacio_no_reporta(self):
        d = self._build_go(contract=GO_CONTRACT.replace("forbids: ['unsafe']",
                                                        'forbids: []'))
        self.assertEqual(self._rules(d), set())

    def test_template_se_salta(self):
        d = self._build_go()
        shutil.copy(os.path.join(d, 'demo.md'),
                    os.path.join(d, 'TEMPLATE-task-contract.md'))
        self.assertEqual(af.audit_forbids(d, self.tmp)['checked'], 1)


class GoMainCli(GoFixture):
    def test_sin_strict_siempre_exit0(self):
        d = self._build_go(gofile='package main\nimport "unsafe"\n\n'
                                   'func Demo(a int) int { return a }\n')
        code = af.main(['audit_forbids.py', d, '--repo-root', self.tmp])
        self.assertEqual(code, 0)

    def test_strict_exit1_con_regla_dura(self):
        d = self._build_go(gofile='package main\nimport "unsafe"\n\n'
                                   'func Demo(a int) int { return a }\n')
        code = af.main(['audit_forbids.py', d, '--repo-root', self.tmp,
                        '--strict'])
        self.assertEqual(code, 1)

    def test_strict_exit0_si_solo_hay_unenforced(self):
        # UNENFORCED es WARNING, no regla dura: no rompe el build ni con
        # --strict.
        d = self._build_go()
        code = af.main(['audit_forbids.py', d, '--repo-root', self.tmp,
                        '--strict'])
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
