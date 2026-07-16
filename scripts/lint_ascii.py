#!/usr/bin/env python3
"""Linter determinista de ASCII para literales en scripts Python.

Recorre scripts_dir/*.py y marca ERROR todo literal string (incluye
f-strings) con caracteres fuera de ASCII (ord > 127), excluyendo docstrings
(primer statement string de modulo/clase/funcion).

Pragmas:
  - Linea: # ascii: allow (permite el literal en esa linea)
  - Modulo: # ascii-lint: skip-file (primeras 5 lineas; salta archivo)

CLI: python scripts/lint_ascii.py [scripts_dir]
  - exit 0 sin ERRORs
  - exit 1 con >=1 ERROR

API: lint_ascii(scripts_dir: str) -> list de findings
  [{'file': '...', 'level': 'ERROR', 'rule': 'ASCII', 'msg': '...'}]
  ordenados por (file, lineno).
"""

import ast
import os
import sys


def _finding(file, msg):
    """Crea un finding ERROR."""
    return {'file': file, 'level': 'ERROR', 'rule': 'ASCII', 'msg': msg}


def _skip_file_pragma(source_text):
    """Detecta # ascii-lint: skip-file en las primeras 5 lineas."""
    lines = source_text.splitlines()
    for line in lines[:5]:
        if '# ascii-lint: skip-file' in line:
            return True
    return False


def _line_allows_ascii(source_lines, lineno):
    """Detecta # ascii: allow en la linea lineno (1-indexed)."""
    if lineno <= 0 or lineno > len(source_lines):
        return False
    line = source_lines[lineno - 1]
    return '# ascii: allow' in line


def _get_codepoint_str(s):
    """Devuelve string con los codepoints no-ASCII en formato U+XXXX."""
    codepoints = []
    for ch in s:
        if ord(ch) > 127:
            codepoints.append('U+{:04X}'.format(ord(ch)))
    return ' '.join(sorted(set(codepoints)))


def _find_docstrings(tree):
    """Devuelve set de ids de nodos que son docstrings."""
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            if hasattr(node, 'body') and len(node.body) > 0:
                first = node.body[0]
                if isinstance(first, ast.Expr):
                    val = first.value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        docstring_ids.add(id(val))
    return docstring_ids


def _find_jstring_constants(tree):
    """Devuelve set de ids de Constant que estan dentro de JoinedStr."""
    jstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant):
                    jstring_ids.add(id(value))
    return jstring_ids


def _check_literal(rel_path, source_lines, lineno, s, kind):
    """Evalua un string literal; devuelve (lineno, finding) o None."""
    if not any(ord(ch) > 127 for ch in s):
        return None
    if _line_allows_ascii(source_lines, lineno):
        return None
    codepoints = _get_codepoint_str(s)
    preview = s[:40].replace('\n', ' ')
    msg = 'linea {}: {} no-ASCII: {} ({}...)'.format(
        lineno, kind, codepoints, preview)
    return (lineno, _finding(rel_path, msg))


def _lint_file(rel_path, source_text, source_lines):
    """Lintea un archivo .py. Devuelve (lista de (lineno, finding), skipped)."""
    if _skip_file_pragma(source_text):
        return [], True
    try:
        tree = ast.parse(source_text)
    except SyntaxError as e:
        lineno = e.lineno or 1
        msg = 'error de sintaxis: linea {}: {}'.format(lineno, e.msg)
        return [(lineno, _finding(rel_path, msg))], False
    entries = []
    docstring_ids = _find_docstrings(tree)
    jstring_ids = _find_jstring_constants(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Docstrings excluidas; partes de f-strings se procesan como JoinedStr
            if id(node) in docstring_ids or id(node) in jstring_ids:
                continue
            entry = _check_literal(rel_path, source_lines, node.lineno,
                                   node.value, 'literal string')
            if entry is not None:
                entries.append(entry)
        elif isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    entry = _check_literal(rel_path, source_lines, value.lineno,
                                           value.value, 'f-string literal')
                    if entry is not None:
                        entries.append(entry)
    return entries, False


def _lint_dir(scripts_dir):
    """Lintea todos los .py bajo scripts_dir.

    Devuelve (findings, skipped_files): findings es lista de
    [{'file','level','rule','msg'}] ordenada por (file, lineno);
    skipped_files es la lista de archivos salteados por skip-file.
    No lanza ante archivos invalidos (reporta en findings).
    """
    scripts_abs = os.path.abspath(scripts_dir)
    if not os.path.isdir(scripts_abs):
        return [], []
    all_entries = []  # (rel_path, lineno, finding)
    skipped_files = []
    py_files = []
    for dirpath, _dirs, files in os.walk(scripts_abs):
        for name in files:
            if name.endswith('.py'):
                py_files.append(os.path.join(dirpath, name))
    py_files.sort()
    for filepath in py_files:
        rel_path = os.path.relpath(filepath, scripts_abs).replace(os.sep, '/')
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                source_text = fh.read()
        except OSError as e:
            all_entries.append((rel_path, 1,
                                _finding(rel_path, 'no se pudo leer: {}'.format(e))))
            continue
        except UnicodeDecodeError as e:
            # Un archivo no-UTF8 es, por definicion, no-ASCII-conforme: se
            # reporta como finding del archivo en vez de tumbar el gate con
            # un traceback (UnicodeDecodeError es ValueError, no OSError, asi
            # que el except OSError de arriba no lo atrapa).
            all_entries.append((rel_path, 1,
                                _finding(rel_path,
                                         'no es UTF-8 valido (no-ASCII-conforme): {}'.format(e))))
            continue
        source_lines = source_text.splitlines()
        entries, skipped = _lint_file(rel_path, source_text, source_lines)
        for lineno, finding in entries:
            all_entries.append((rel_path, lineno, finding))
        if skipped:
            skipped_files.append(rel_path)
    # Orden determinista por (archivo, linea) ANTES de emitir
    all_entries.sort(key=lambda e: (e[0], e[1]))
    findings = [finding for _rel, _lineno, finding in all_entries]
    return findings, skipped_files


def lint_ascii(scripts_dir):
    """Lintea todos los .py bajo scripts_dir.

    Devuelve lista de findings [{'file','level','rule','msg'}] ordenada por
    (file, lineno), vacia si todo es conforme. No lanza ante archivos
    invalidos (reporta en findings).
    """
    findings, _skipped = _lint_dir(scripts_dir)
    return findings


def main(argv):
    scripts_dir = argv[1] if len(argv) > 1 else 'scripts'
    if not os.path.isdir(scripts_dir):
        print("ERROR: no existe el directorio: {}".format(scripts_dir))
        return 1
    findings, skipped_files = _lint_dir(scripts_dir)
    errors = [f for f in findings if f['level'] == 'ERROR']
    if findings:
        for f in findings:
            print("{} [{}] {}: {}".format(
                f['level'], f['rule'], f['file'], f['msg']))
    else:
        print("OK: todos los scripts son ASCII-conformes")
    n_files = len([f for f in os.listdir(scripts_dir) if f.endswith('.py')])
    if skipped_files:
        print("\nArchivos salteados (# ascii-lint: skip-file): {}".format(
            ', '.join(skipped_files)))
    print("\nResumen: {} error(es) en {} archivo(s)".format(
        len(errors), n_files))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
