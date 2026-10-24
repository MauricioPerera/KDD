#!/usr/bin/env python3
"""Gate que ejecuta el ``test_command`` declarado en cada contrato.

Unico gate del repo cuyo ``forbids`` NO incluye ``subprocess``: su intent es
literalmente ejecutar el ``test_command`` (texto libre del contrato) y leer su
exit code. Ver ``knowledge/contracts/test-command-gate.md``, seccion
'Por que este gate rompe la convencion forbids: subprocess'.

API publica (fijada por ``tests/test_validate_test_commands.py``):
    extract_test_command(text) -> str|None
    collect_contracts(directory) -> list[dict]
    run_test_command(cmd, cwd, timeout, capture=False) -> dict
    run_all(contracts_dir, repo_root, timeout=180, deduplicate=False, workers=1) -> list[dict]
    main(argv) -> int
"""

import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from validate_contracts import parse_frontmatter


def extract_test_command(text):
    """Read the same frontmatter value accepted by ``validate_contracts``.

    The shared parser accepts both quoted and plain scalars. A second regex
    parser silently skipped otherwise valid contracts, producing false PASS.
    """
    metadata, _ = parse_frontmatter(text)
    value = metadata.get('test_command') if isinstance(metadata, dict) else None
    return value if isinstance(value, str) and value else None


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
        metadata, _ = parse_frontmatter(text)
        target = metadata.get('target', '') if isinstance(metadata, dict) else ''
        scope = metadata.get('test_scope') if isinstance(metadata, dict) else None
        if scope not in ('product', 'infrastructure'):
            scope = ('infrastructure' if isinstance(target, str) and
                     target.replace('\\', '/').startswith(
                         ('scripts/', 'tools/', 'plugins/', '.github/', 'tests/'))
                     else 'product')
        items.append({'path': path, 'test_command': cmd, 'scope': scope})
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


def run_test_command(cmd, cwd, timeout, capture=False):
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
        proc = subprocess.run(tokens, cwd=cwd, timeout=timeout,
                              capture_output=capture, text=True)
    except FileNotFoundError:
        return {'exit_code': None, 'ok': False, 'error': 'not_found'}
    except subprocess.TimeoutExpired:
        return {'exit_code': None, 'ok': False, 'error': 'timeout'}
    result = {'exit_code': proc.returncode, 'ok': proc.returncode == 0, 'error': None}
    if capture:
        result['stdout'] = proc.stdout or ''
        result['stderr'] = proc.stderr or ''
    return result


def run_all(contracts_dir, repo_root, timeout=180, deduplicate=False, workers=1):
    """Run every command with opt-in concurrency and per-call exact grouping."""
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('workers must be an integer between 1 and 8')
    items = collect_contracts(contracts_dir)
    representatives = {}
    scheduled = []
    for index, item in enumerate(items):
        key = item['test_command'] if deduplicate else index
        if key not in representatives:
            representatives[key] = index
            scheduled.append(index)

    def execute(index):
        started = time.perf_counter()
        outcome = run_test_command(items[index]['test_command'], cwd=repo_root,
                                   timeout=timeout, capture=True)
        return outcome, time.perf_counter() - started

    if workers == 1:
        outcomes = {index: execute(index) for index in scheduled}
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {index: pool.submit(execute, index) for index in scheduled}
            outcomes = {index: future.result() for index, future in futures.items()}
    results = []
    for index, item in enumerate(items):
        key = item['test_command'] if deduplicate else index
        first = representatives[key]
        ran, elapsed = outcomes[first]
        shared = items[first]['path'] if first != index else None
        results.append({
            'path': item['path'],
            'scope': item['scope'],
            'test_command': item['test_command'],
            'exit_code': ran['exit_code'],
            'ok': ran['ok'],
            'error': ran['error'],
            'stdout': ran.get('stdout', ''),
            'stderr': ran.get('stderr', ''),
            'shared_from': shared,
            'duration_seconds': 0 if shared else elapsed,
        })
    return results


def _print_results(results):
    counts = {'product': {'PASS': 0, 'FAIL': 0},
              'infrastructure': {'PASS': 0, 'FAIL': 0}}
    for item in results:
        status = 'PASS' if item['ok'] else 'FAIL'
        counts[item['scope']][status] += 1
        if item['ok']:
            print('PASS [{}] {}'.format(item['scope'], item['path']))
        else:
            if item['error'] is not None:
                detail = item['error']
            else:
                detail = 'exit_code={}'.format(item['exit_code'])
            print('FAIL [{}] {}: {}'.format(item['scope'], item['path'], detail))
        output = (item.get('stdout', '') + item.get('stderr', '')).strip()
        if item.get('shared_from'):
            print('  SHARED {}'.format(item['shared_from']))
        elif output:
            print('  TEST_OUTPUT (informativo; el exit code es el veredicto):')
            for line in output.splitlines():
                print('    ' + line)
    for scope in ('infrastructure', 'product'):
        group = counts[scope]
        if not any(group.values()):
            print('SKIP [{}] no contracts with test_command'.format(scope))
        print('Summary: {} PASS={} FAIL={} SKIP={}'.format(
            scope, group['PASS'], group['FAIL'], int(not any(group.values()))))
    shared_count = sum(item.get('shared_from') is not None for item in results)
    print('Executions: contracts={} commands={} shared={} seconds={:.3f}'.format(
        len(results), len(results) - shared_count, shared_count,
        sum(item.get('duration_seconds', 0) for item in results)))
    return 1 if any(not item['ok'] for item in results) else 0


def main(argv):
    """Entry point CLI. Devuelve 0 si todos PASS, 1 si alguno FAIL o no hay."""
    contracts_dir = argv[1] if len(argv) > 1 else 'knowledge/contracts'
    repo_root = argv[2] if len(argv) > 2 else '.'
    timeout = 180
    workers = 1
    if '--workers' in argv:
        index = argv.index('--workers')
        try:
            workers = int(argv[index + 1])
            if not 1 <= workers <= 8:
                raise ValueError('workers out of range')
        except (IndexError, ValueError):
            print('FAIL: --workers requires an integer between 1 and 8')
            return 1
    if '--timeout' in argv:
        index = argv.index('--timeout')
        if index + 1 >= len(argv):
            print('FAIL: --timeout requiere segundos')
            return 1
        try:
            timeout = int(argv[index + 1])
        except ValueError:
            print('FAIL: --timeout debe ser un entero')
            return 1
        if timeout <= 0:
            print('FAIL: --timeout debe ser positivo')
            return 1
    started = time.perf_counter()
    results = run_all(contracts_dir, repo_root, timeout=timeout,
                      deduplicate='--deduplicate' in argv, workers=workers)
    if not results:
        print('FAIL: no contracts with test_command found in {}'.format(contracts_dir))
        return 1
    status = _print_results(results)
    print('Scheduling: workers={} wall_seconds={:.3f}'.format(
        workers, time.perf_counter() - started))
    return status


if __name__ == '__main__':
    sys.exit(main(sys.argv))
