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
    run_all(contracts_dir, repo_root, timeout=600, deduplicate=False, workers=1) -> list[dict]
    main(argv) -> int
"""

import os
import json
import time
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor
from validate_contracts import parse_frontmatter
from process_tree import run as run_process


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


def _command_tokens(cmd):
    posix = os.name != 'nt'
    tokens = shlex.split(cmd, posix=posix)
    return tokens if posix else [_strip_quotes(token) for token in tokens]


def _trusted_suite_command(tokens, cwd, trusted_bundle, temporary):
    if (trusted_bundle is not None and len(tokens) >= 2
            and re.fullmatch(r'python(?:3(?:\.\d+)?)?(?:\.exe)?', Path(tokens[0]).name.lower())
            and (Path(cwd) / tokens[1]).resolve() == (Path(cwd) / 'scripts/run_test_suite.py').resolve()):
        report_path = Path(temporary) / 'suite.json'
        return [sys.executable, '-I', '-X', 'utf8',
                str(Path(trusted_bundle) / 'run_test_suite.py'), *tokens[2:],
                '--report-json', str(report_path)], report_path
    return tokens, None


def run_test_command(cmd, cwd, timeout, capture=False, *, trusted_bundle=None):
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
    try:
        tokens = _command_tokens(cmd)
    except ValueError:
        return {'exit_code': None, 'ok': False, 'error': 'not_found'}
    try:
        with tempfile.TemporaryDirectory(prefix='kdd-command-evidence-') as temporary:
            tokens, report_path = _trusted_suite_command(tokens, cwd, trusted_bundle, temporary)
            proc = run_process(tokens, cwd=cwd, timeout=timeout,
                               capture_output=capture, text=True, encoding='utf-8', errors='replace',
                               env=dict(os.environ, PYTHONUTF8='1'))
            if report_path is not None:
                import run_test_suite as suite
                report = json.loads(report_path.read_text(encoding='utf-8'))
                if not report.get('expected_ids') or suite.validate_report(report['expected_ids'], report) or not report.get('ok'):
                    return {'exit_code': proc.returncode or 1, 'ok': False, 'error': None,
                            'stdout': proc.stdout or '', 'stderr': proc.stderr or ''}
    except FileNotFoundError:
        return {'exit_code': None, 'ok': False, 'error': 'not_found'}
    except subprocess.TimeoutExpired:
        return {'exit_code': None, 'ok': False, 'error': 'timeout'}
    except (OSError, ValueError) as exc:
        return {'exit_code': None, 'ok': False, 'error': 'not_found', 'stderr': str(exc)}
    result = {'exit_code': proc.returncode, 'ok': proc.returncode == 0, 'error': None}
    if capture:
        result['stdout'] = proc.stdout or ''
        result['stderr'] = proc.stderr or ''
    return result


def _run_item(item, repo_root, timeout, *, trusted_bundle=None):
    try:
        if 'test_timeout' in item:
            from oracle_execution import declared_timeout
            timeout = declared_timeout(item, timeout)
        if 'oracle_metadata' in item:
            from oracle_execution import execute_oracle
            return execute_oracle(item['oracle_metadata'], repo_root, timeout)
        options = {'trusted_bundle': trusted_bundle} if trusted_bundle is not None else {}
        return run_test_command(item['test_command'], cwd=repo_root, timeout=timeout, capture=True, **options)
    except (ValueError, ImportError) as exc:
        return {'exit_code': 1, 'ok': False, 'error': str(exc), 'executed_tests': 0}


def parse_exclusive_commands(raw):
    """Decode only the JSON transport; inventory validation precedes execution."""
    try:
        return json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError('exclusive commands must be valid JSON') from exc


def _exclusive_commands(value, items):
    if type(value) not in (list, tuple):
        raise ValueError('exclusive commands must be a list or tuple')
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError('exclusive commands must contain nonempty strings')
    selected = set(value)
    if len(selected) != len(value):
        raise ValueError('exclusive commands must not contain duplicates')
    if selected - {item['test_command'] for item in items}:
        raise ValueError('exclusive command is absent from the inventory')
    return selected


def _schedule(scheduled, exclusive, execute, workers):
    outcomes = {index: execute(index) for index in scheduled if index in exclusive}
    remaining = [index for index in scheduled if index not in exclusive]
    if workers == 1:
        outcomes.update({index: execute(index) for index in remaining})
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {index: pool.submit(execute, index) for index in remaining}
            outcomes.update({index: future.result() for index, future in futures.items()})
    return outcomes



def _item_key(item, index, deduplicate):
    if not deduplicate:
        return index
    if 'oracle_metadata' in item:
        return json.dumps(item['oracle_metadata'], sort_keys=True, default=str)
    return item['test_command'], item.get('test_timeout')


def run_all(contracts_dir, repo_root, timeout=600, deduplicate=False, workers=1, *, trusted_bundle=None, exclusive_commands=()):
    """Run every command with opt-in concurrency and per-call exact grouping."""
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('workers must be an integer between 1 and 8')
    items = collect_contracts(contracts_dir)
    exclusive = _exclusive_commands(exclusive_commands, items)
    representatives = {}
    scheduled = []
    for index, item in enumerate(items):
        key = _item_key(item, index, deduplicate)
        if key not in representatives:
            representatives[key] = index
            scheduled.append(index)

    def execute(index):
        started = time.perf_counter()
        outcome = _run_item(items[index], repo_root, timeout, trusted_bundle=trusted_bundle)
        return outcome, time.perf_counter() - started

    exclusive_indices = {index for index in scheduled if items[index]['test_command'] in exclusive}
    outcomes = _schedule(scheduled, exclusive_indices, execute, workers)
    results = []
    for index, item in enumerate(items):
        key = _item_key(item, index, deduplicate)
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
        if 'oracle_metadata' in item:
            results[-1].update(executed_tests=ran['executed_tests'],
                               runner=item['oracle_metadata'].get('test_runner'),
                               runner_evidence=ran.get('evidence'))
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
        if item.get('shared_from'):
            print('  SHARED {}'.format(item['shared_from']))
        elif output:
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
    shared_count = sum(item.get('shared_from') is not None for item in results)
    print('Executions: contracts={} commands={} shared={} seconds={:.3f}'.format(
        len(results), len(results) - shared_count, shared_count,
        sum(item.get('duration_seconds', 0) for item in results)))
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


def _save_timings(argv, results):
    if '--timings-json' not in argv:
        return True
    index = argv.index('--timings-json')
    if index + 1 >= len(argv):
        print('FAIL: --timings-json requires a file path')
        return False
    try:
        _write_timings(argv[index + 1], results)
        return True
    except OSError as exc:
        print('FAIL: cannot write timings: ' + str(exc))
        return False


def main(argv):
    """Entry point CLI. Devuelve 0 si todos PASS, 1 si alguno FAIL o no hay."""
    from validation_runtime import prepare_runtime
    prepare_runtime()
    contracts_dir = argv[1] if len(argv) > 1 else 'knowledge/contracts'
    repo_root = argv[2] if len(argv) > 2 else '.'
    timeout = 600
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
            timeout = float(argv[index + 1])
        except ValueError:
            print('FAIL: --timeout debe ser un entero')
            return 1
        if timeout <= 0:
            print('FAIL: --timeout debe ser positivo')
            return 1
    started = time.perf_counter()
    try:
        exclusive = ()
        if '--exclusive-commands-json' in argv:
            index = argv.index('--exclusive-commands-json')
            if index + 1 >= len(argv):
                raise ValueError('exclusive commands JSON argument is missing')
            exclusive = parse_exclusive_commands(argv[index + 1])
        results = run_all(contracts_dir, repo_root, timeout=timeout,
                         deduplicate='--deduplicate' in argv, workers=workers,
                         exclusive_commands=exclusive)
    except ValueError as exc:
        print('FAIL: ' + str(exc))
        return 1
    if not results:
        print('FAIL: no contracts with test_command found in {}'.format(contracts_dir))
        return 1
    status = _print_results(results)
    print('Scheduling: workers={} wall_seconds={:.3f}'.format(
        workers, time.perf_counter() - started))
    return max(status, int(not _save_timings(argv, results)))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
