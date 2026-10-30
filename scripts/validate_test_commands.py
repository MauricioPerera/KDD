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
    run_all(contracts_dir, repo_root, timeout=120) -> list[dict]
    main(argv) -> int
"""

import os
import json
import time
import shlex
import subprocess
import sys
from validate_contracts import parse_frontmatter
from validation_runtime import prepare_runtime


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
        items.append(_configured_item(path, cmd, scope, metadata))
    items.sort(key=lambda item: item['path'])
    return items


def _configured_item(path, command, scope, metadata):
    item = {'path': path, 'test_command': command, 'scope': scope}
    if 'test_timeout' in metadata:
        from oracle_execution import declared_timeout
        try:
            item['test_timeout'] = declared_timeout(metadata)
        except ValueError:
            item['test_timeout'] = metadata['test_timeout']
    if 'test_runner' in metadata:
        item['oracle_metadata'] = metadata
    return item


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


def _run_item(item, repo_root, timeout):
    try:
        if 'test_timeout' in item:
            from oracle_execution import declared_timeout
            timeout = declared_timeout(item, timeout)
        if 'oracle_metadata' in item:
            from oracle_execution import execute_oracle
            return execute_oracle(item['oracle_metadata'], repo_root, timeout)
        return run_test_command(item['test_command'], cwd=repo_root, timeout=timeout, capture=True)
    except ValueError as exc:
        return {'exit_code': 1, 'ok': False, 'error': str(exc), 'executed_tests': 0}


def run_all(contracts_dir, repo_root, timeout=180, progress=None):
    """Corre ``run_test_command`` para cada contrato, desde ``repo_root``."""
    results = []
    for item in collect_contracts(contracts_dir):
        if progress:
            progress('RUN', item)
        started = time.perf_counter()
        ran = _run_item(item, repo_root, timeout)
        results.append({
            'path': item['path'],
            'scope': item['scope'],
            'test_command': item['test_command'],
            'exit_code': ran['exit_code'],
            'ok': ran['ok'],
            'error': ran['error'],
            'stdout': ran.get('stdout', ''),
            'stderr': ran.get('stderr', ''),
            'duration_seconds': time.perf_counter() - started,
        })
        if 'oracle_metadata' in item:
            results[-1].update(executed_tests=ran['executed_tests'],
                               runner=item['oracle_metadata'].get('test_runner'),
                               runner_evidence=ran.get('evidence'))
        if progress:
            progress('RESULT', results[-1])
    return results


def _print_results(results):
    counts = {'product': {'PASS': 0, 'FAIL': 0},
              'infrastructure': {'PASS': 0, 'FAIL': 0}}
    for item in results:
        status = result_status(item)
        counts[item['scope']]['PASS' if item['ok'] else 'FAIL'] += 1
        print('  duration={:.3f}s'.format(item.get('duration_seconds', 0)))
        if 'runner' in item:
            print('  oracle_execution: runner={} executed_tests={}'.format(
                item['runner'], item['executed_tests']))
        if item['ok']:
            print('PASS [{}] {}'.format(item['scope'], item['path']))
        else:
            if item['error'] is not None:
                detail = item['error']
            else:
                detail = 'exit_code={}'.format(item['exit_code'])
            print('{} [{}] {}: {}'.format(status, item['scope'], item['path'], detail))
        output = (item.get('stdout', '') + item.get('stderr', '')).strip()
        if output:
            label = ('salida capturada; se exigen exit y evidencia del runner' if 'runner' in item else
                     'informativo; el exit code es el veredicto')
            print('  TEST_OUTPUT ({}):'.format(label))
            for line in output.splitlines():
                print('    ' + line)
    for scope in ('infrastructure', 'product'):
        group = counts[scope]
        if not any(group.values()):
            print('SKIP [{}] no contracts with test_command'.format(scope))
        print('Summary: {} PASS={} FAIL={} SKIP={}'.format(
            scope, group['PASS'], group['FAIL'], int(not any(group.values()))))
    return 1 if any(not item['ok'] for item in results) else 0



def result_status(item):
    return 'TIMEOUT' if item['error'] == 'timeout' else 'PASS' if item['ok'] else 'FAIL'


def _progress(phase, item):
    if phase == 'RUN':
        print('RUN [{}] {}'.format(item['scope'], item['path']), flush=True)
    else:
        print('{} [{}] {} duration={:.3f}s'.format(
            result_status(item), item['scope'], item['path'], item['duration_seconds']), flush=True)


def _write_timings(path, results):
    fields = ('path', 'scope', 'duration_seconds', 'exit_code', 'error')
    data = {'results': [dict({key: item[key] for key in fields}, status=result_status(item))
                        for item in results],
            'total_duration_seconds': sum(item['duration_seconds'] for item in results)}
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2)


def main(argv):
    """Entry point CLI. Devuelve 0 si todos PASS, 1 si alguno FAIL o no hay."""
    prepare_runtime()
    contracts_dir = argv[1] if len(argv) > 1 else 'knowledge/contracts'
    repo_root = argv[2] if len(argv) > 2 else '.'
    timeout = 180
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
    results = run_all(contracts_dir, repo_root, timeout=timeout, progress=_progress)
    if not results:
        print('FAIL: no contracts with test_command found in {}'.format(contracts_dir))
        return 1
    if '--timings-json' in argv:
        index = argv.index('--timings-json')
        if index + 1 >= len(argv):
            print('FAIL: --timings-json requires a file path')
            return 1
        try:
            _write_timings(argv[index + 1], results)
        except OSError as exc:
            print('FAIL: cannot write timings: ' + str(exc))
            return 1
    return _print_results(results)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
