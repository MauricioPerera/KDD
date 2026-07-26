#!/usr/bin/env python3
"""Gate de supresiones de lint introducidas en el DIFF (Contrato: lint-suppression-gate).

Un implementador (agente efimero) puede esquivar un gate de lint (p.ej. clippy,
ver linter_gate.py del proyecto hermano ccdd-gate) sin arreglar el codigo:
agregando un ``#[allow(clippy::...)]``/``#![allow(clippy::...)]`` encima del
lint en vez de resolverlo. El mismo problema de fondo que resuelven los tests
congelados (``tests_sha256``) para property-tests, pero nadie lo cubria para
supresiones de lint.

Escanea un DIFF unificado (``git diff``), no el archivo completo: solo lineas
AGREGADAS (prefijo ``+``, sin contar el header ``+++``) cuentan como finding.
Una supresion preexistente que solo se desplaza de linea (aparece como
contexto sin prefijo ``+``/``-``) NO se reporta -- por eso este gate necesita
el diff y no un escaneo estatico como scan_secrets.py.

Limitacion documentada (no resuelta a proposito, ver docstring de
``scan_diff``): si una linea con supresion se borra y se vuelve a agregar
identica por churn del hunk circundante (edicion cerca, sin tocar esa linea
en si), el diff la muestra como ``-``+``+`` y este gate SI la reporta aunque
el implementador no la haya escrito el mismo. Falso positivo aceptado: mas
seguro sobre-reportar una supresion nueva que dejarla pasar.

Ver knowledge/contracts/lint-suppression-gate.md para el contrato completo y
tests/test_scan_lint_suppressions.py para el oraculo congelado.
"""

import re
import sys


# (rule_name, compiled_regex). Cada patron matchea la supresion completa.
# Hoy solo clippy (Rust); el registro queda abierto a sumar mas sin romper
# la interfaz (mismo patron que PATTERNS en scan_secrets.py).
PATTERNS = [
    ('CLIPPY_ALLOW', re.compile(r'#!?\[\s*allow\(\s*clippy::[A-Za-z0-9_:]+')),
]

_HUNK_RE = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')


def iter_added_lines(diff_text):
    """[(file, line_no, content)] por cada linea AGREGADA de un diff unificado.

    `file` es la ruta del lado nuevo (``+++ b/<path>``, sin el prefijo
    ``b/``); `line_no` es 1-indexed en el archivo nuevo. Archivos borrados
    (``+++ /dev/null``) no producen entradas (no hay lado nuevo que revisar).
    Tolera diffs vacios o mal formados: nunca lanza, en el peor caso no
    encuentra hunks y devuelve ``[]``.
    """
    current_file = None
    line_no = None
    out = []
    for raw in diff_text.splitlines():
        if raw.startswith('+++ '):
            path = raw[4:].strip()
            if path.startswith('b/'):
                path = path[2:]
            current_file = None if path in ('/dev/null', '') else path
            line_no = None
            continue
        if raw.startswith('@@'):
            m = _HUNK_RE.match(raw)
            line_no = int(m.group(1)) if m else None
            continue
        if current_file is None or line_no is None:
            continue
        if raw.startswith('+'):
            out.append((current_file, line_no, raw[1:]))
            line_no += 1
        elif raw.startswith('-'):
            pass  # linea borrada: no existe en el archivo nuevo, no avanza line_no
        elif raw.startswith('\\'):
            pass  # "\ No newline at end of file": no es contenido, no avanza
        else:
            line_no += 1  # linea de contexto (espacio inicial, o vacia)
    return out


def scan_diff(diff_text):
    """Findings ERROR: supresiones de PATTERNS en lineas AGREGADAS del diff.

    Devuelve ``[{'file','level','rule','msg'}]`` ordenado por (file, rule,
    msg). ``msg`` incluye el numero de linea y el texto matcheado completo
    (a diferencia de scan_secrets.py, no hay nada sensible que truncar aca).
    """
    findings = []
    for file, line_no, content in iter_added_lines(diff_text):
        for rule, regex in PATTERNS:
            m = regex.search(content)
            if m:
                findings.append({
                    'file': file,
                    'level': 'ERROR',
                    'rule': rule,
                    'msg': 'line {}: nueva supresion de lint agregada: {}'.format(
                        line_no, m.group(0).strip()),
                })
    findings.sort(key=lambda f: (f['file'], f['rule'], f['msg']))
    return findings


def main(argv):
    """CLI: python scripts/scan_lint_suppressions.py [diff_file]

    Sin argumento, lee el diff de stdin (uso tipico:
    ``git diff <base>...HEAD -- <archivos> | python scripts/scan_lint_suppressions.py``).
    Imprime cada finding y un resumen. Exit 0 sin findings, 1 con >=1.
    """
    if len(argv) > 1:
        try:
            with open(argv[1], 'r', encoding='utf-8', errors='ignore') as fh:
                diff_text = fh.read()
        except OSError as e:
            print("ERROR: no se pudo leer {}: {}".format(argv[1], e))
            return 1
    else:
        diff_text = sys.stdin.read()

    findings = scan_diff(diff_text)
    for f in findings:
        print("{} [{}] {}: {}".format(f['level'], f['rule'], f['file'], f['msg']))
    print("Resumen: {} finding(s)".format(len(findings)))
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
