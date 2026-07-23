"""Auditor de seals debiles (Contrato: seal-audit).

Herramienta ADVISORY: detecta oraculos congelados que el sello
(``tests_sha256``) certifica como integros pero que no pueden fallar --
sin asserts reales (``assert True`` no cuenta), sin funciones de test, o
sin referenciar jamas al target. El sello garantiza integridad, no fuerza;
este auditor reporta la ausencia mecanica de fuerza. La calidad semantica
de un assert no-trivial queda fuera (trabajo de mutation testing).

Solo LEE archivos. Sin subprocess, sin red, sin LLM. Deteccion por ``ast``
(stdlib), nunca regex sobre el codigo. ASCII puro (lo audita
``lint_ascii``). Ver ``knowledge/contracts/seal-audit.md``.

API (congelada por ``tests/test_audit_seals.py``):
  Reglas (constantes str): WEAK_TESTS_MISSING, WEAK_TESTS_EMPTY,
    WEAK_TESTS_UNPARSEABLE, WEAK_NO_TEST_FUNCTIONS, WEAK_NO_ASSERTS,
    WEAK_TARGET_UNREFERENCED.
  ``audit_contract(contract_path, repo_root) -> list[dict]`` -- findings
    ``{'contract','rule','msg'}`` de UN contrato (lista vacia = sano).
  ``audit_seals(contracts_dir='knowledge/contracts', repo_root='.') ->
    {'findings': [...], 'checked': int}`` -- recorre ``*.md`` (salta
    ``TEMPLATE-*``), findings ordenados por (contract, rule).
  ``main(argv) -> int`` -- argv estilo ``sys.argv``; posicional opcional
    contracts_dir, flags ``--repo-root DIR`` y ``--strict``. Sin
    ``--strict`` SIEMPRE 0 (advisory); con ``--strict`` 1 si hay findings.
"""

import ast
import os
import sys

from validate_contracts import parse_frontmatter

WEAK_TESTS_MISSING = 'WEAK_TESTS_MISSING'
WEAK_TESTS_EMPTY = 'WEAK_TESTS_EMPTY'
WEAK_TESTS_UNPARSEABLE = 'WEAK_TESTS_UNPARSEABLE'
WEAK_NO_TEST_FUNCTIONS = 'WEAK_NO_TEST_FUNCTIONS'
WEAK_NO_ASSERTS = 'WEAK_NO_ASSERTS'
WEAK_TARGET_UNREFERENCED = 'WEAK_TARGET_UNREFERENCED'


def _finding(contract, rule, msg):
    """Construye un finding de un contrato."""
    return {'contract': contract, 'rule': rule, 'msg': msg}


def _contract_targets(data):
    """Devuelve (tests, target) o None si el contrato no es auditable.

    No es auditable si no hay frontmatter o faltan las claves tests/target
    (la estructura la vigila validate_contracts, no este auditor).
    """
    if not data:
        return None
    tests = data.get('tests')
    target = data.get('target')
    if not isinstance(tests, str) or not isinstance(target, str):
        return None
    return tests, target


def _read_tests(tests_path):
    """Devuelve (status, src). status in {'missing','empty','unparseable','ok'}.

    Nunca lanza: archivo ausente o ilegible por I/O -> 'missing'; presente
    pero no decodificable como utf-8 -> 'unparseable' (mismo significado que
    un SyntaxError del AST). AUDIT-05 H-3.
    """
    if not os.path.isfile(tests_path):
        return 'missing', ''
    try:
        with open(tests_path, 'r', encoding='utf-8') as fh:
            src = fh.read()
    except UnicodeDecodeError:
        return 'unparseable', ''
    except OSError:
        return 'missing', ''
    if not src.strip():
        return 'empty', ''
    return 'ok', src


def _has_test_functions(tree):
    """True si hay FunctionDef/AsyncFunctionDef cuyo nombre empieza con test."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith('test'):
                return True
    return False


def _is_real_assert(node):
    """True si el nodo es un assert real.

    ast.Assert cuyo test NO es ast.Constant (``assert True`` no cuenta), o
    ast.Call cuyo func es ast.Attribute con attr que empieza con 'assert'
    (cubre self.assertEqual, assertRaises, etc.).
    """
    if isinstance(node, ast.Assert):
        return not isinstance(node.test, ast.Constant)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr.startswith('assert'):
            return True
    return False


def _has_real_asserts(tree):
    """True si el arbol contiene al menos un assert real."""
    for node in ast.walk(tree):
        if _is_real_assert(node):
            return True
    return False


def _py_findings(tree, contract, target_stem, needs_ref):
    """Findings del analisis AST de un tests file Python.

    No hay cortocircuito entre estas reglas: pueden coexistir.
    """
    findings = []
    if not _has_test_functions(tree):
        findings.append(_finding(contract, WEAK_NO_TEST_FUNCTIONS,
                                 'no test functions in tests file'))
    if not _has_real_asserts(tree):
        findings.append(_finding(contract, WEAK_NO_ASSERTS,
                                 'no real asserts in tests file'))
    if needs_ref:
        findings.append(_finding(contract, WEAK_TARGET_UNREFERENCED,
                                 'target stem not in tests source: '
                                 + target_stem))
    findings.sort(key=lambda f: f['rule'])
    return findings


def _audit(contract_path, repo_root):
    """Nucleo: devuelve (auditable, findings).

    auditable=False significa que el contrato no tiene frontmatter o le
    faltan las claves tests/target -> no cuenta en ``checked`` y no genera
    findings. Nunca lanza: el problema es un finding o (False, []).
    """
    contract = os.path.basename(contract_path)
    try:
        with open(contract_path, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        # contrato no-utf8 (UnicodeDecodeError es ValueError, no OSError):
        # no auditable, sin crash. AUDIT-05 H-3.
        return False, []
    data, _body = parse_frontmatter(text)
    targets = _contract_targets(data)
    if targets is None:
        return False, []
    tests_rel, target_rel = targets
    status, src = _read_tests(os.path.join(repo_root, tests_rel))
    if status == 'missing':
        return True, [_finding(contract, WEAK_TESTS_MISSING,
                               'tests file not found: ' + tests_rel)]
    if status == 'empty':
        return True, [_finding(contract, WEAK_TESTS_EMPTY,
                               'tests file empty: ' + tests_rel)]
    if status == 'unparseable':
        return True, [_finding(contract, WEAK_TESTS_UNPARSEABLE,
                               'tests file not utf-8: ' + tests_rel)]
    target_stem = os.path.splitext(os.path.basename(target_rel))[0]
    is_self = os.path.normpath(tests_rel) == os.path.normpath(target_rel)
    needs_ref = (not is_self) and (target_stem not in src)
    if os.path.splitext(tests_rel)[1] != '.py':
        # Tests no-Python: el analisis AST es Python-only.
        if needs_ref:
            return True, [_finding(contract, WEAK_TARGET_UNREFERENCED,
                                   'target stem not in tests source: '
                                   + target_stem)]
        return True, []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return True, [_finding(contract, WEAK_TESTS_UNPARSEABLE,
                               'tests file not parseable: ' + tests_rel)]
    return True, _py_findings(tree, contract, target_stem, needs_ref)


def audit_contract(contract_path, repo_root):
    """Findings de UN contrato (lista vacia = sano). Ver ``_audit``."""
    _auditable, findings = _audit(contract_path, repo_root)
    return findings


def audit_seals(contracts_dir='knowledge/contracts', repo_root='.'):
    """Audita todos los ``*.md`` del dir (salta ``TEMPLATE-*``).

    Devuelve ``{'findings': [...], 'checked': int}``. ``checked`` cuenta
    solo contratos auditables (con frontmatter y claves tests/target).
    findings ordenados por (contract, rule). Nunca lanza.
    """
    findings = []
    checked = 0
    try:
        names = sorted(os.listdir(contracts_dir))
    except OSError:
        return {'findings': [], 'checked': 0}
    for name in names:
        if not name.endswith('.md') or name.startswith('TEMPLATE-'):
            continue
        auditable, cf = _audit(os.path.join(contracts_dir, name), repo_root)
        if not auditable:
            continue
        checked += 1
        findings.extend(cf)
    findings.sort(key=lambda f: (f['contract'], f['rule']))
    return {'findings': findings, 'checked': checked}


def main(argv):
    """CLI. Posicional opcional contracts_dir; flags --repo-root, --strict.

    Sin ``--strict`` SIEMPRE devuelve 0 (advisory). Con ``--strict``
    devuelve 1 si hay findings, 0 limpio.
    """
    contracts_dir = 'knowledge/contracts'
    repo_root = '.'
    strict = False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == '--strict':
            strict = True
            i += 1
        elif a == '--repo-root':
            if i + 1 < len(argv):
                repo_root = argv[i + 1]
            i += 2
        elif a.startswith('--repo-root='):
            repo_root = a.split('=', 1)[1]
            i += 1
        elif not a.startswith('-'):
            contracts_dir = a
            i += 1
        else:
            i += 1
    result = audit_seals(contracts_dir=contracts_dir, repo_root=repo_root)
    findings = result['findings']
    for f in findings:
        print('%s: %s - %s' % (f['contract'], f['rule'], f['msg']))
    print('seal-audit: %d checked, %d findings%s' % (
        result['checked'], len(findings), ' [strict]' if strict else ''))
    if strict and findings:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))