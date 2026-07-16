#!/usr/bin/env python3
"""Gate que ejecuta el ``test_command`` declarado en cada contrato.

Unico gate del repo cuyo ``forbids`` NO incluye ``subprocess``: su intent es
literalmente ejecutar el ``test_command`` (texto libre del contrato) y leer su
exit code. Ver ``knowledge/contracts/test-command-gate.md``, seccion
'Por que este gate rompe la convencion forbids: subprocess'.

API publica (fijada por ``tests/test_validate_test_commands.py``):
    extract_test_command(text) -> str|None
    collect_contracts(directory) -> list[dict]
    run_test_command(cmd, cwd, timeout) -> dict
    run_all(contracts_dir, repo_root, timeout=120) -> list[dict]
    main(argv) -> int
"""

import os
import re
import shlex
import subprocess
import sys


def _frontmatter(text):
    """Devuelve el bloque YAML entre los delimitadores ``---`` iniciales, o ''.

    Normaliza CRLF/CR a LF antes de matchear para que un contrato guardado con
    CRLF (Windows) se parsee igual que con LF, coherente con el dialecto
    ``splitlines()`` de validate_contracts.py (Contrato: test-command-gate).
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    return m.group(1) if m else ''


def _unescape_double(value):
    """YAML double-quoted: solo convierte ``\\"`` en ``"``.

    Las demas barras (ej. ``C:\\Python``) se conservan literales — el oraculo
    trata la ruta de ``sys.executable`` en Windows como texto, no como escapes
    YAML completos.
    """
    return re.sub(r'\\"', '"', value)


def extract_test_command(text):
    """Valor de ``test_command`` en el frontmatter (comillas simples o dobles).

    None si la clave no esta o esta vacia. Soporta escapes ``\\"`` (doble
    comilla) y ``''`` (simple comilla duplicada) segun el escalar YAML.
    """
    fm = _frontmatter(text)
    if not fm:
        return None
    m = re.search(
        r'^test_command:\s*"((?:\\.|[^"\\])*)"\s*$',
        fm,
        re.MULTILINE,
    )
    if m:
        value = _unescape_double(m.group(1))
        return value if value else None
    m = re.search(
        r"^test_command:\s*'((?:[^']|'')*)'\s*$",
        fm,
        re.MULTILINE,
    )
    if m:
        value = m.group(1).replace("''", "'")
        return value if value else None
    return None


def collect_contracts(directory):
    """Lista ``[{'path','test_command'}]`` por cada ``*.md`` con test_command.

    Excluye archivos que empiezan con ``TEMPLATE-`` y los que no tienen
    ``test_command`` no vacio. Ordenado por ``path`` ascendente.
    """
    items = []
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    for name in names:
        if not name.endswith('.md'):
            continue
        if name.startswith('TEMPLATE-'):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            # I/O o bytes invalidos para UTF-8: no se puede leer el contrato.
            # Se maneja explicito (se salta) en vez de tumbar el gate con un
            # traceback. UnicodeDecodeError es ValueError, no OSError.
            continue
        cmd = extract_test_command(text)
        if not cmd:
            continue
        items.append({'path': path, 'test_command': cmd})
    items.sort(key=lambda item: item['path'])
    return items


def _strip_quotes(token):
    """Quita una capa de comillas envolventes coincidentes (posix=False).

    En Windows (posix=False) shlex deja las comillas literales dentro del
    token; esto normaliza ``"C:\\...exe"`` -> ``C:\\...exe`` para que
    subprocess encuentre el ejecutable.
    """
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token


def run_test_command(cmd, cwd, timeout):
    """Ejecuta ``cmd`` (string) partido con ``shlex.split`` via subprocess.run.

    Devuelve ``{'exit_code','ok','error'}``:
      - exit 0 -> ``{'exit_code': 0, 'ok': True, 'error': None}``
      - exit !=0 -> ``{'exit_code': N, 'ok': False, 'error': None}``
      - timeout -> ``{'exit_code': None, 'ok': False, 'error': 'timeout'}``
      - no encontrado -> ``{'exit_code': None, 'ok': False, 'error': 'not_found'}``

    En Windows se usa ``posix=False`` para que las barras invertidas de rutas
    como ``C:\\Python314\\python.exe`` no sean tratadas como escapes y comidas
    por shlex; luego se quita una capa de comillas envolventes por token para
    replicar el descascarado que ``posix=True`` haria en POSIX.
    """
    posix = os.name != 'nt'
    try:
        tokens = shlex.split(cmd, posix=posix)
    except ValueError:
        return {'exit_code': None, 'ok': False, 'error': 'not_found'}
    if not posix:
        tokens = [_strip_quotes(t) for t in tokens]
    try:
        proc = subprocess.run(tokens, cwd=cwd, timeout=timeout)
    except FileNotFoundError:
        return {'exit_code': None, 'ok': False, 'error': 'not_found'}
    except subprocess.TimeoutExpired:
        return {'exit_code': None, 'ok': False, 'error': 'timeout'}
    return {'exit_code': proc.returncode, 'ok': proc.returncode == 0, 'error': None}


def run_all(contracts_dir, repo_root, timeout=120):
    """Corre ``run_test_command`` para cada contrato, desde ``repo_root``."""
    results = []
    for item in collect_contracts(contracts_dir):
        ran = run_test_command(item['test_command'], cwd=repo_root, timeout=timeout)
        results.append({
            'path': item['path'],
            'test_command': item['test_command'],
            'exit_code': ran['exit_code'],
            'ok': ran['ok'],
            'error': ran['error'],
        })
    return results


def main(argv):
    """Entry point CLI. Devuelve 0 si todos PASS, 1 si alguno FAIL o no hay."""
    contracts_dir = argv[1] if len(argv) > 1 else 'knowledge/contracts'
    repo_root = argv[2] if len(argv) > 2 else '.'

    results = run_all(contracts_dir, repo_root)
    if not results:
        print('FAIL: no contracts with test_command found in {}'.format(contracts_dir))
        return 1

    exit_code = 0
    for item in results:
        if item['ok']:
            print('PASS {}'.format(item['path']))
        else:
            exit_code = 1
            if item['error'] is not None:
                detail = item['error']
            else:
                detail = 'exit_code={}'.format(item['exit_code'])
            print('FAIL {}: {}'.format(item['path'], detail))
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv))