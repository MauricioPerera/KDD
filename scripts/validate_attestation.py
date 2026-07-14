#!/usr/bin/env python3
"""Gate de atestacion de reportes locales (Contrato: attestation-gate).

Verifica el envelope mini-YAML al tope de cada
``.agents/logs/<task>-REPORT.md`` (evidencia LOCAL, gitignorada). El envelope
liga la evidencia a una identidad (agente/modelo), a un comando+exit_code, y a
DOS hashes recomputables: el del propio output pegado abajo del envelope, y el
del contrato (``knowledge/contracts/<task>.md``) tal como estaba al verificar.

Herramienta de verificacion local del PM -- NO es paso de CI (la evidencia que
audita es local y gitignorada; un runner de CI nunca la ve). Solo stdlib:
``hashlib``, ``os``, ``re``, ``sys``.

API publica (oraculo congelado en tests/test_validate_attestation.py):
  ``REQUIRED_KEYS`` -- tupla de las 9 claves obligatorias del envelope.
  ``parse_envelope(text) -> (dict|None, str)``
  ``validate_report(path, repo_root) -> [findings]``
  ``validate_directory(logs_dir, repo_root='.') -> [findings]``
  ``main(argv) -> int``
"""

import hashlib
import os
import re
import sys

REQUIRED_KEYS = (
    'task',
    'agent',
    'model',
    'command',
    'exit_code',
    'output_sha256',
    'contract_sha256',
    'repo_head',
    'timestamp',
)

_REPORT_SUFFIX = '-REPORT.md'
_TEMPLATE_REPORT = 'TEMPLATE-REPORT.md'


def _lf_normalize(text):
    """Misma normalizacion LF que validate_contracts.py --hash."""
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _sha256(text):
    return hashlib.sha256(_lf_normalize(text).encode('utf-8')).hexdigest()


def parse_envelope(text):
    """Devuelve ``(dict|None, body)`` del envelope mini-YAML al tope de ``text``.

    El envelope es el bloque entre los primeros DOS delimitadores ``---`` en su
    propia linea. ``dict`` mapea ``{clave: valor_string}`` (valor sin espacios
    laterales). ``body`` es todo lo que sigue despues del segundo delimitador,
    sin la primera linea en blanco si la hay.

    ``(None, text)`` si ``text`` no empieza con ``---\\n`` o no hay un segundo
    delimitador ``---`` en su propia linea. Nunca lanza excepcion.
    """
    if not isinstance(text, str) or not text.startswith('---\n'):
        return None, text
    lines = text.split('\n')
    # lines[0] == '---' (garantizado por el startswith).
    close_idx = None
    for i in range(1, len(lines)):
        if lines[i] == '---':
            close_idx = i
            break
    if close_idx is None:
        return None, text
    data = {}
    for line in lines[1:close_idx]:
        if not line.strip():
            continue
        match = re.match(r'^([^:]+):(.*)$', line)
        if match:
            data[match.group(1).strip()] = match.group(2).strip()
    body_lines = lines[close_idx + 1:]
    if body_lines and body_lines[0] == '':
        body_lines = body_lines[1:]
    return data, '\n'.join(body_lines)


def _finding(file_name, level, rule, msg):
    return {'file': file_name, 'level': level, 'rule': rule, 'msg': msg}


def _expected_task(file_name):
    if file_name.endswith(_REPORT_SUFFIX):
        return file_name[:-len(_REPORT_SUFFIX)]
    return file_name


def validate_report(path, repo_root='.'):
    """Valida un unico ``<task>-REPORT.md``. Ver docstring del modulo."""
    file_name = os.path.basename(path)
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            text = handle.read()
    except OSError:
        return [_finding(file_name, 'ERROR', 'ENVELOPE_MISSING',
                         'no se pudo leer el reporte')]

    data, body = parse_envelope(text)
    if data is None:
        return [_finding(file_name, 'WARNING', 'ENVELOPE_MISSING',
                         'sin envelope de atestacion (formato pre-gate)')]

    findings = []

    def present(key):
        return key in data and data[key] != ''

    # MISSING_KEY: una por cada clave ausente o vacia.
    for key in REQUIRED_KEYS:
        if not present(key):
            findings.append(_finding(
                file_name, 'ERROR', 'MISSING_KEY',
                "clave obligatoria ausente o vacia: '{}'".format(key)))

    # TASK_MISMATCH: solo si 'task' esta presente (no-vacio).
    if present('task'):
        if data['task'] != _expected_task(file_name):
            findings.append(_finding(
                file_name, 'ERROR', 'TASK_MISMATCH',
                "task='{}' no coincide con el nombre de archivo '{}'".format(
                    data['task'], _expected_task(file_name))))

    # EXIT_CODE_*: solo si 'exit_code' esta presente.
    if present('exit_code'):
        if not re.match(r'^-?\d+$', data['exit_code']):
            findings.append(_finding(
                file_name, 'ERROR', 'EXIT_CODE_INVALID',
                "exit_code={!r} no es un entero literal".format(
                    data['exit_code'])))
        elif int(data['exit_code']) != 0:
            findings.append(_finding(
                file_name, 'ERROR', 'EXIT_CODE_NONZERO',
                "exit_code={} distinto de 0".format(data['exit_code'])))

    # OUTPUT_HASH_MISMATCH: solo si 'output_sha256' esta presente.
    if present('output_sha256'):
        actual = _sha256(body)
        if actual != data['output_sha256']:
            findings.append(_finding(
                file_name, 'ERROR', 'OUTPUT_HASH_MISMATCH',
                "output_sha256={} no coincide con el hash real del body "
                "({})".format(data['output_sha256'], actual)))

    # CONTRACT_*: solo si 'task' y 'contract_sha256' estan presentes.
    if present('task') and present('contract_sha256'):
        contract_path = os.path.join(
            repo_root, 'knowledge', 'contracts', data['task'] + '.md')
        if not os.path.isfile(contract_path):
            findings.append(_finding(
                file_name, 'ERROR', 'CONTRACT_MISSING',
                "no existe knowledge/contracts/{}.md bajo repo_root".format(
                    data['task'])))
        else:
            with open(contract_path, 'r', encoding='utf-8') as handle:
                contract_text = handle.read()
            actual = _sha256(contract_text)
            if actual != data['contract_sha256']:
                findings.append(_finding(
                    file_name, 'ERROR', 'CONTRACT_HASH_MISMATCH',
                    "contract_sha256={} no coincide con el hash real del "
                    "contrato ({})".format(data['contract_sha256'], actual)))

    findings.sort(key=lambda f: f['rule'])
    return findings


def validate_directory(logs_dir, repo_root='.'):
    """Valida cada ``*-REPORT.md`` de ``logs_dir`` (no recursivo).

    Excluye ``TEMPLATE-REPORT.md``. Directorio inexistente -> ``[]``.
    Ordenado por ``(file, rule)``.
    """
    if not os.path.isdir(logs_dir):
        return []
    findings = []
    for name in os.listdir(logs_dir):
        if not name.endswith(_REPORT_SUFFIX):
            continue
        if name == _TEMPLATE_REPORT:
            continue
        full = os.path.join(logs_dir, name)
        if not os.path.isfile(full):
            continue
        findings.extend(validate_report(full, repo_root))
    findings.sort(key=lambda f: (f['file'], f['rule']))
    return findings


def main(argv):
    """``argv[1]``=logs_dir (default ``.agents/logs``), ``argv[2]``=repo_root
    (default ``.``). Imprime cada finding. Devuelve 0 si no hay ERROR, 1 si hay
    >=1 ERROR (los WARNING como ``ENVELOPE_MISSING`` NO bloquean)."""
    logs_dir = argv[1] if len(argv) > 1 else '.agents/logs'
    repo_root = argv[2] if len(argv) > 2 else '.'
    findings = validate_directory(logs_dir, repo_root)
    for f in findings:
        print('{} [{}] {}: {}'.format(f['level'], f['rule'], f['file'], f['msg']))
    if any(f['level'] == 'ERROR' for f in findings):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))