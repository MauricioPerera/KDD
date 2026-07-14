#!/usr/bin/env python3
"""Gate de secretos filtrados en codigo generado (Contrato: secret-scan-gate).

Escaneo determinista (regex stdlib, sin red/subprocess/LLM) de archivos de
texto buscando prefijos de credenciales conocidas (AWS, GitHub, Slack, Google,
Stripe) y bloques de private key. NO deteccion de alta entropia generica, para
no generar falsos positivos masivos contra los ``tests_sha256`` de 64 hex chars
que ya viven en ``knowledge/contracts/*.md`` de este mismo repo.

Ver knowledge/contracts/secret-scan-gate.md para el contrato completo y
tests/test_scan_secrets.py para el oraculo congelado.
"""

import os
import re
import sys


# (rule_name, compiled_regex). Cada patron matchea el secreto completo.
PATTERNS = [
    ('AWS_KEY', re.compile(r'AKIA[0-9A-Z]{16}')),
    ('GITHUB_TOKEN', re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}')),
    ('SLACK_TOKEN', re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}')),
    ('GOOGLE_API_KEY', re.compile(r'AIza[0-9A-Za-z_-]{35}')),
    ('STRIPE_KEY', re.compile(r'(sk|pk)_live_[A-Za-z0-9]{20,}')),
    ('PRIVATE_KEY_BLOCK', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
]


def scan_text(text):
    """Matches de PATTERNS sobre text, con numero de linea 1-indexed.

    Devuelve ``[{'rule','match','line'}]`` ordenado por (line, rule). Nunca
    lanza excepcion sobre texto arbitrario.
    """
    findings = []
    for index, line in enumerate(text.splitlines(), start=1):
        for rule, regex in PATTERNS:
            for m in regex.finditer(line):
                findings.append({'rule': rule, 'match': m.group(0), 'line': index})
    findings.sort(key=lambda f: (f['line'], f['rule']))
    return findings


def scan_file(path):
    """Findings ERROR de scan_text sobre el contenido de path (UTF-8, ignore).

    El ``msg`` NUNCA incluye el secreto completo: solo los primeros 8 chars +
    ``'...'`` para no filtrarlo en logs de CI.
    """
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            text = fh.read()
    except OSError:
        return []
    findings = []
    for f in scan_text(text):
        secret = f['match']
        msg = "line {}: {}...".format(f['line'], secret[:8])
        findings.append({'file': path, 'level': 'ERROR', 'rule': f['rule'], 'msg': msg})
    return findings


def scan_directory(directory, extensions=('.py', '.js', '.ts', '.md', '.json')):
    """Recorre directory recursivamente y escanea archivos con extensions dadas.

    Ignora directorios ocultos (nombre empieza con ``.``), ``__pycache__`` y
    ``node_modules``. Directorio inexistente -> ``[]`` (no es error del gate).
    """
    if not os.path.isdir(directory):
        return []
    exts = tuple(e.lower() for e in extensions)
    findings = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')
                   and d not in ('__pycache__', 'node_modules')]
        for name in files:
            if name.lower().endswith(exts):
                findings.extend(scan_file(os.path.join(root, name)))
    findings.sort(key=lambda f: f['file'])
    return findings


def main(argv):
    """argv[1:] son directorios a escanear (default ['src', 'tests']).

    Imprime cada finding como ``"ERROR [<rule>] <file>: <msg>"`` y devuelve 0
    si no hay findings, 1 si hay >=1.
    """
    dirs = argv[1:] if len(argv) > 1 else ['src', 'tests']
    findings = []
    for d in dirs:
        findings.extend(scan_directory(d))
    for f in findings:
        print("ERROR [{}] {}: {}".format(f['rule'], f['file'], f['msg']))
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))