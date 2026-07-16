#!/usr/bin/env python3
"""Gate de formato de mensaje de commit (Contrato 31).

Implementacion del validador de formato de commit contra
Conventional Commits v1.0.0 y reglas por defecto de commitlint.
"""

import json
import os
import re
import sys


def parse_commit_message(msg):
    """Parse a commit message into its components.

    Returns dict with keys: type, scope, breaking, description, header, body.
    Returns None if the header does not match the grammar.
    """
    if not msg or not msg.strip():
        return None

    lines = msg.split('\n')
    header = lines[0]

    # Regex: tipo(scope)?!?: descripción
    # tipo: word characters, hyphens, underscores
    # scope: optional, in parentheses
    # !: optional breaking marker
    # :: colon + space
    # descripción: rest of line (non-empty)
    pattern = r'^([a-zA-Z0-9_-]+)(\([^)]+\))?(!)?:\s(.+)$'
    match = re.match(pattern, header)

    if not match:
        return None

    type_ = match.group(1)
    scope_match = match.group(2)
    breaking = match.group(3) is not None
    description = match.group(4)

    # Scope without parentheses
    scope = None
    if scope_match:
        scope = scope_match[1:-1]  # Remove the parentheses

    # Body: lines from index 2 onward (line 3 and beyond)
    body = ''
    if len(lines) > 2:
        body = '\n'.join(lines[2:])

    return {
        'type': type_,
        'scope': scope,
        'breaking': breaking,
        'description': description,
        'header': header,
        'body': body,
    }


def check_commit_message(msg, config):
    """Check a commit message against configuration rules.

    Returns a list of findings, each a dict with keys: level, rule, msg.
    """
    findings = []

    parsed = parse_commit_message(msg)

    # If header is malformed, return only this finding
    if parsed is None:
        findings.append({
            'level': 'ERROR',
            'rule': 'HEADER_MALFORMED',
            'msg': 'el header no matchea la gramatica tipo(scope)?!?: descripcion',
        })
        return findings

    # TYPE_UNKNOWN
    if parsed['type'] not in config['types']:
        findings.append({
            'level': 'ERROR',
            'rule': 'TYPE_UNKNOWN',
            'msg': "tipo '{}' no esta en los tipos permitidos: {}".format(
                parsed['type'], ', '.join(config['types'])),
        })

    # SCOPE_REQUIRED
    if config.get('scope_required', False) and parsed['scope'] is None:
        findings.append({
            'level': 'ERROR',
            'rule': 'SCOPE_REQUIRED',
            'msg': 'la convencion exige scope y no fue provisto',
        })

    # BLANK_LINE_MISSING
    # If there's a line 2 (index 1) and it's not blank, there's an issue.
    # This catches both: (a) header directly followed by body on line 2,
    # and (b) multi-line messages without blank line separation.
    lines = msg.split('\n')
    if len(lines) > 1:
        line_2 = lines[1]
        if line_2.strip() != '':
            findings.append({
                'level': 'ERROR',
                'rule': 'BLANK_LINE_MISSING',
                'msg': 'falta una linea en blanco entre el header y el cuerpo',
            })

    # SUBJECT_TOO_LONG
    if len(parsed['header']) > config['max_subject_length']:
        findings.append({
            'level': 'WARNING',
            'rule': 'SUBJECT_TOO_LONG',
            'msg': "el header mide {} caracteres, excede el maximo {}".format(
                len(parsed['header']), config['max_subject_length']),
        })

    # SUBJECT_TRAILING_PERIOD
    if parsed['description'].endswith('.'):
        findings.append({
            'level': 'WARNING',
            'rule': 'SUBJECT_TRAILING_PERIOD',
            'msg': 'la descripcion no deberia terminar en punto',
        })

    return findings


def main(argv):
    """Main entry point.

    argv[0]: path to config JSON
    Optional: --message <text> | --file <path> | stdin

    Returns 0 if no errors, 1 if any ERROR.
    """
    if len(argv) < 1:
        print("ERROR [CONFIG_MISSING]: falta la ruta al config JSON", file=sys.stderr)
        return 1

    config_path = argv[0]

    # Load config
    if not os.path.exists(config_path):
        print("ERROR [CONFIG_MISSING]: config no encontrado: {}".format(config_path))
        print()
        print("Resumen: 1 error(es), 0 warning(s)")
        return 1

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print("ERROR [CONFIG_INVALID]: config no es JSON valido: {}".format(str(e)))
        print()
        print("Resumen: 1 error(es), 0 warning(s)")
        return 1

    # Config valido como JSON pero sin la forma esperada: un config que no es
    # objeto o que omite claves que check_commit_message indexa directo
    # ('types', 'max_subject_length') producira KeyError/TypeError (traceback)
    # en vez de un finding. Reportarlo como CONFIG_INVALID + exit 1.
    required_keys = ('types', 'max_subject_length')
    if not isinstance(config, dict):
        print("ERROR [CONFIG_INVALID]: config no es un objeto JSON (se esperaba "
              "un dict con al menos: {})".format(', '.join(required_keys)))
        print()
        print("Resumen: 1 error(es), 0 warning(s)")
        return 1
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        print("ERROR [CONFIG_INVALID]: config sin claves requeridas: {}".format(
            ', '.join(missing_keys)))
        print()
        print("Resumen: 1 error(es), 0 warning(s)")
        return 1

    # Determine message source
    msg = None
    if '--message' in argv:
        idx = argv.index('--message')
        if idx + 1 < len(argv):
            msg = argv[idx + 1]
    elif '--file' in argv:
        idx = argv.index('--file')
        if idx + 1 < len(argv):
            file_path = argv[idx + 1]
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    msg = f.read()
            except IOError as e:
                print("ERROR [MESSAGE_FILE_MISSING]: no se pudo leer el archivo del "
                      "mensaje: {}".format(str(e)))
                print()
                print("Resumen: 1 error(es), 0 warning(s)")
                return 1
    else:
        # Read from stdin
        msg = sys.stdin.read()

    # Check message
    findings = check_commit_message(msg, config)

    # Print findings
    for finding in findings:
        level = finding['level']
        rule = finding['rule']
        msg_text = finding['msg']
        print("{} [{}]: {}".format(level, rule, msg_text))

    # Print summary
    n_errors = sum(1 for f in findings if f['level'] == 'ERROR')
    n_warnings = sum(1 for f in findings if f['level'] == 'WARNING')

    print()
    print("Resumen: {} error(es), {} warning(s)".format(n_errors, n_warnings))

    return 1 if n_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
