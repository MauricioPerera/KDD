#!/usr/bin/env python3
"""Preflight: dry-run local de los 12 gates de KDD (Contrato: preflight).

Diagnostico opt-in (NO es un gate de CI, misma familia que
``benchmark_gates.py``). Dos modos:

  Modo full (``contract is None``): corre los 12 gates (los 11 de Nivel 1 +
  ``validate_attestation``, el local-only) contra el repo actual via
  ``run_gate`` y reporta cuales fallarian, ANTES de delegar trabajo a un
  agente. Reporta TODOS aunque el primero falle (es dry-run, no short-circuit).

  Modo contract (``contract='<task>'``): NO corre los 12 gates. Corre 3
  chequeos acotados a ``knowledge/contracts/<task>.md`` -- frontmatter,
  seal del oraculo, test_command -- en ese orden. Un chequeo previo fallido
  marca los siguientes como fallidos (se saltean, no se ejecutan).

  API (fijada por el oraculo congelado ``tests/test_preflight.py``):
    ``ALL_GATES`` -- ``LEVEL1_GATES`` + ``['validate_attestation']`` (12).
    ``run_gate`` -- referencia de modulo inicializada a
      ``mcp_gate_dispatch.run_gate`` (indireccion deliberada: el oraculo la
      parchea; ``run_preflight`` con ``runner=None`` la resuelve EN CADA
      llamada, no la captura en un default).
    ``run_preflight(repo_root='.', contract=None, runner=None) -> dict``
      ``{'mode', 'overall_ok', 'results', 'lines'}``.
    ``main(argv) -> int`` -- flags ``--repo-root DIR`` y ``--contract NAME``.

Cero dependencias externas: stdlib + modulos hermanos de ``scripts/``. Sin
SDK ``mcp``. ``run_preflight`` NUNCA lanza por un gate/chequeo fallido: los
fallos son informacion (``exit_code`` != 0); el unico canal de veredicto es
``overall_ok`` / el exit code de ``main``.
"""

import hashlib
import os
import shlex
import subprocess
import sys

import mcp_gate_dispatch
from validate_contracts import parse_frontmatter

# Derivada del dispatch, nunca hardcodeada aparte: un gate nuevo en
# GATE_SPECS aparece aqui solo con actualizar el dispatch.
ALL_GATES = list(mcp_gate_dispatch.LEVEL1_GATES) + ['validate_attestation']

# Indireccion deliberada: el oraculo parchea ``preflight.run_gate``.
# ``run_preflight`` con ``runner=None`` la resuelve EN CADA llamada via
# lookup del global de modulo, no la captura en un default de parametro.
run_gate = mcp_gate_dispatch.run_gate

_CONTRACT_CHECKS = ['frontmatter', 'seal', 'test_command']
_TIMEOUT = 120


def _status(exit_code):
    """PASS si 0, TIMEOUT si None, FAIL otherwise."""
    if exit_code == 0:
        return 'PASS'
    if exit_code is None:
        return 'TIMEOUT'
    return 'FAIL'


def _format_lines(results, total):
    """Una linea por item (nombre + estado) + linea resumen <pasados>/<total>."""
    lines = []
    passed = 0
    for name, res in results.items():
        code = res['exit_code']
        if code == 0:
            passed += 1
        lines.append('{name}: {status}'.format(name=name,
                                               status=_status(code)))
    lines.append('Summary: {passed}/{total}'.format(passed=passed,
                                                    total=total))
    return lines


def _result(exit_code, stdout='', stderr=''):
    return {'exit_code': exit_code, 'stdout': stdout, 'stderr': stderr}


def _skipped(name):
    """Chequeo no ejecutado porque uno previo fallo."""
    return _result(1, stderr='{n} skipped: prior check failed'.format(n=name))


def _normalize_lf(text):
    """\r\n -> \n y \r suelto -> \n (bit-compatible con validate_contracts)."""
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _parse_contract(contract_path):
    """Devuelve (exit_code, stderr, data). exit_code 0 -> data es dict.

    Chequea que el contrato exista y que su frontmatter declare ``tests``,
    ``tests_sha256`` y ``test_command``. Parseo CRLF-safe (splitlines de
    validate_contracts), valores con o sin comillas (_parse_scalar).
    """
    if not os.path.isfile(contract_path):
        return 1, 'contract not found: {}'.format(contract_path), None
    try:
        with open(contract_path, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except OSError as exc:
        return 1, 'cannot read contract: {}'.format(exc), None
    data, _body = parse_frontmatter(text)
    if not isinstance(data, dict):
        return 1, 'frontmatter not parseable', None
    fm_keys = ['tests', 'tests_sha256', 'test_command']
    missing = [k for k in fm_keys if not data.get(k)]
    if missing:
        return 1, 'missing frontmatter keys: {}'.format(', '.join(missing)), None
    return 0, '', data


def _check_seal(repo_root, data):
    """sha256 del archivo ``tests`` (LF-normalizado, utf-8) == tests_sha256."""
    tests_rel = data['tests']
    tests_path = os.path.join(repo_root, tests_rel)
    if not os.path.isfile(tests_path):
        return _result(1, stderr='tests file not found: {}'.format(tests_path))
    try:
        with open(tests_path, 'r', encoding='utf-8') as fh:
            content = fh.read()
    except OSError as exc:
        return _result(1, stderr='cannot read tests: {}'.format(exc))
    actual = hashlib.sha256(_normalize_lf(content).encode('utf-8')).hexdigest()
    expected = data['tests_sha256']
    if actual != expected:
        return _result(1, stderr='seal mismatch: expected {} got {}'.format(
            expected, actual))
    return _result(0)


def _check_test_command(repo_root, data):
    """Ejecuta ``test_command`` (cwd=repo_root, timeout 120) y propaga exit code.

    shlex.split con posix=False en Windows (rutas con barras invertidas); se
    quita una capa de comillas envolventes por token, como
    validate_test_commands. Nunca lanza: fallo es informacion.
    """
    cmd = data['test_command']
    posix = os.name != 'nt'
    try:
        tokens = shlex.split(cmd, posix=posix)
    except ValueError:
        return _result(1, stderr='cannot parse test_command: {}'.format(cmd))
    if not posix:
        tokens = [_strip_quotes(t) for t in tokens]
    try:
        proc = subprocess.run(tokens, cwd=repo_root, capture_output=True,
                              text=True, timeout=_TIMEOUT)
    except subprocess.TimeoutExpired:
        return _result(None, stderr='timeout after {}s'.format(_TIMEOUT))
    except FileNotFoundError:
        return _result(1, stderr='command not found: {}'.format(tokens[0]))
    except OSError as exc:
        return _result(1, stderr='cannot run command: {}'.format(exc))
    return _result(proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _strip_quotes(token):
    """Quita una capa de comillas envolventes coincidentes (posix=False)."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token


def _run_contract_mode(repo_root, contract):
    """3 chequeos (frontmatter, seal, test_command) sobre el contrato dado."""
    contract_path = os.path.join(repo_root, 'knowledge', 'contracts',
                                 '{}.md'.format(contract))
    results = {}
    ec, err, data = _parse_contract(contract_path)
    results['frontmatter'] = _result(ec, stderr=err)
    if ec != 0:
        results['seal'] = _skipped('seal')
        results['test_command'] = _skipped('test_command')
        return _contract_payload(results)
    results['seal'] = _check_seal(repo_root, data)
    if results['seal']['exit_code'] != 0:
        results['test_command'] = _skipped('test_command')
    else:
        results['test_command'] = _check_test_command(repo_root, data)
    return _contract_payload(results)


def _contract_payload(results):
    overall_ok = all(r['exit_code'] == 0 for r in results.values())
    lines = _format_lines(results, len(_CONTRACT_CHECKS))
    return {'mode': 'contract', 'overall_ok': overall_ok,
            'results': results, 'lines': lines}


def run_preflight(repo_root='.', contract=None, runner=None):
    """Corre el preflight y devuelve ``{'mode','overall_ok','results','lines'}``.

    Modo full (``contract is None``): los 12 gates via ``runner`` (default:
    la referencia de modulo ``run_gate``, resuelta EN CADA llamada). Modo
    contract: 3 chequeos, jamas invoca ``runner``. Nunca lanza por un fallo.
    """
    if contract is not None:
        return _run_contract_mode(repo_root, contract)
    if runner is None:
        runner = run_gate
    results = {}
    for name in ALL_GATES:
        results[name] = runner(name, {}, repo_root=repo_root)
    overall_ok = all(r['exit_code'] == 0 for r in results.values())
    lines = _format_lines(results, len(ALL_GATES))
    return {'mode': 'full', 'overall_ok': overall_ok,
            'results': results, 'lines': lines}


def main(argv):
    """Entry point CLI. Devuelve 0 si overall_ok, 1 si no."""
    repo_root = '.'
    contract = None
    i = 1
    while i < len(argv):
        if argv[i] == '--repo-root' and i + 1 < len(argv):
            repo_root = argv[i + 1]
            i += 2
        elif argv[i] == '--contract' and i + 1 < len(argv):
            contract = argv[i + 1]
            i += 2
        else:
            i += 1
    res = run_preflight(repo_root=repo_root, contract=contract)
    for line in res['lines']:
        print(line)
    return 0 if res['overall_ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))