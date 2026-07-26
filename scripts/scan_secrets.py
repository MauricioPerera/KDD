#!/usr/bin/env python3
"""Gate de secretos filtrados en codigo generado (Contrato: secret-scan-gate).

Escaneo determinista (regex stdlib, sin red/subprocess/LLM) de archivos de
texto buscando prefijos de credenciales conocidas (AWS, GitHub, Slack, Google,
Stripe) y bloques de private key. NO deteccion de alta entropia generica, para
no generar falsos positivos masivos contra los ``tests_sha256`` de 64 hex chars
que ya viven en ``knowledge/contracts/*.md`` de este mismo repo.

La COBERTURA es la lista ``DEFAULT_EXTENSIONS``: lo que no esta ahi no se mira.
Por eso el gate avisa (``SECRETS_NO_FILES_SCANNED``) cuando un directorio tiene
archivos y ninguno matcheo -- el modo de fallo peligroso de un escaner de
secretos no es reportar de mas, es salir verde sin haber leido nada.

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


# Extensiones escaneadas por defecto. La lista ES la cobertura del gate: una
# extension ausente no se reporta como "sin secretos", simplemente NUNCA se mira.
# Historia: hasta esta version la lista era ('.py','.js','.ts','.md','.json'), asi
# que en un proyecto Rust/Go/Java el gate escaneaba CERO archivos y salia 0 -- un
# gate de seguridad reportando verde sin haber leido nada. Cubre los lenguajes con
# backend en el gate (ver metrics_treesitter) mas los formatos de config/script
# donde las credenciales aparecen igual de seguido.
DEFAULT_EXTENSIONS = (
    # lenguajes
    '.py', '.pyi', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.rs', '.go',
    '.java', '.cs', '.php', '.rb', '.kt', '.kts', '.c', '.h', '.cpp', '.cc',
    '.cxx', '.hpp', '.swift',
    # config, scripts y texto
    '.md', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.env',
    '.properties', '.sh', '.bash', '.zsh', '.ps1', '.sql', '.tf', '.tfvars',
    '.xml', '.gradle', '.txt',
)

SECRETS_NO_FILES_SCANNED = 'SECRETS_NO_FILES_SCANNED'


def scan_directory(directory, extensions=None):
    """Recorre directory recursivamente y escanea archivos con extensions dadas.

    `extensions` None usa ``DEFAULT_EXTENSIONS``. Ignora directorios ocultos
    (nombre empieza con ``.``), ``__pycache__`` y ``node_modules``. Directorio
    inexistente -> ``[]`` (no es error del gate).

    Si el directorio TIENE archivos pero ninguno matchea la extension, agrega un
    finding WARNING ``SECRETS_NO_FILES_SCANNED``: el modo de fallo peligroso de
    este gate no es reportar de mas, es salir en verde sin haber mirado nada.
    """
    if not os.path.isdir(directory):
        return []
    exts = tuple(e.lower() for e in
                 (DEFAULT_EXTENSIONS if extensions is None else extensions))
    findings = []
    seen_any = False
    scanned = 0
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')
                   and d not in ('__pycache__', 'node_modules')]
        for name in files:
            seen_any = True
            if name.lower().endswith(exts):
                scanned += 1
                findings.extend(scan_file(os.path.join(root, name)))
    findings.sort(key=lambda f: f['file'])
    if seen_any and scanned == 0:
        findings.append({
            'file': directory, 'level': 'WARNING',
            'rule': SECRETS_NO_FILES_SCANNED,
            'msg': 'el directorio tiene archivos pero ninguno matchea las '
                   'extensiones escaneadas: este gate NO miro nada aqui'})
    return findings


def main(argv):
    """argv[1:] son directorios a escanear (default ['src']).

    Imprime cada finding como ``"<LEVEL> [<rule>] <file>: <msg>"``. Devuelve 1
    si hay algun ERROR (una credencial), 0 si no. El WARNING de cobertura
    (``SECRETS_NO_FILES_SCANNED``) se imprime pero NO rompe el build: avisa que
    el gate no miro nada, no que haya un secreto.
    """
    dirs = argv[1:] if len(argv) > 1 else ['src']
    findings = []
    for d in dirs:
        findings.extend(scan_directory(d))
    for f in findings:
        print("{} [{}] {}: {}".format(
            f.get('level', 'ERROR'), f['rule'], f['file'], f['msg']))
    return 1 if any(f.get('level', 'ERROR') == 'ERROR' for f in findings) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))