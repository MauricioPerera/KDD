"""Bind managed test execution to explicit, inventoried test files.

Approved oracle code and the host are trusted; this is not a sandbox. Evidence
comes from controlled runners, never from arbitrary test stdout.
"""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from oracle_inventory import inventory_paths, local_file


def declared_timeout(metadata, fallback=180):
    value = metadata.get('test_timeout', fallback)
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    if type(value) is not int or not 0 < value <= 3600:
        raise ValueError('test_timeout must be an integer in 1..3600')
    return value


def _tokens(command):
    if not isinstance(command, str) or not command:
        raise ValueError('test_command is required')
    tokens = shlex.split(command, posix=os.name != 'nt')
    if os.name == 'nt':
        tokens = [token[1:-1] if len(token) > 1 and token[0] == token[-1]
                  and token[0] in "\"'" else token for token in tokens]
    return tokens


def _python_names(tokens):
    if len(tokens) < 4 or tokens[1:3] != ['-m', 'unittest']:
        raise ValueError('Expected python -m unittest with explicit modules/files')
    executable = tokens[0]
    alias = re.fullmatch(r'python(?:(3)(?:\.(\d+))?)?(?:\.exe)?', executable, re.I)
    if alias:
        major, minor = alias.groups()
        if (major and int(major) != sys.version_info.major or
                minor and int(minor) != sys.version_info.minor):
            raise ValueError('Declared Python version does not match the managed runtime')
    else:
        if Path(executable).resolve() != Path(sys.executable).resolve():
            raise ValueError('Unrecognized Python executable')
    names = tokens[3:]
    files = [name if name.endswith('.py') else name.replace('.', '/') + '.py' for name in names]
    return names, files


def _invocation(metadata, root):
    inventory = inventory_paths(metadata, required=True)
    tokens = _tokens(metadata.get('test_command'))
    runner = metadata.get('test_runner')
    if runner == 'python-unittest':
        names, files = _python_names(tokens)
    elif runner == 'node-test':
        if len(tokens) < 3 or tokens[0] not in ('node', 'node.exe') or tokens[1] != '--test':
            raise ValueError('Expected node --test with explicit files')
        names, files = tokens[2:], tokens[2:]
    else:
        raise ValueError('Unsupported or missing test_runner')
    if metadata['tests'] not in files or len(set(files)) != len(files):
        raise ValueError('Command must include the declared oracle exactly once')
    for name in files:
        if name.startswith('-'):
            raise ValueError('Runner options are not test file selections')
        if name not in inventory or not local_file(root, name).is_file():
            raise ValueError('Selected test is not an inventoried regular file: ' + name)
    return runner, names, files


def _command(runner, names, root, temp):
    scripts = Path(__file__).resolve().parent
    if runner == 'python-unittest':
        return [sys.executable, '-I', '-B', '-X', 'pycache_prefix=' + str(temp / 'cache'),
                str(scripts / 'unittest_oracle_runner.py'), str(root), str(temp / 'result.json'), *names]
    node = shutil.which('node')
    if not node:
        raise ValueError('Node runtime not found')
    return [node, '--test', '--test-reporter=' + (scripts / 'node_oracle_reporter.mjs').as_uri(), *names]


def _evidence(runner, completed, temp):
    if runner == 'python-unittest':
        return json.loads((temp / 'result.json').read_text(encoding='utf-8'))
    summaries = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    return {'files': {item['file']: {'executed': item['counts']['passed'],
                                   'skipped': item['counts']['skipped'] + item['counts']['todo'],
                                   'ok': item['success']}
                      for item in summaries}}


def _verified_count(evidence, files, root):
    total = 0
    for name in files:
        item = evidence['files'].get(str((root / name).resolve()))
        if not isinstance(item, dict) or item.get('ok') is not True or item.get('skipped') != 0:
            raise ValueError('Missing, failed or omitted oracle cases: ' + name)
        count = item.get('executed')
        if type(count) is not int or count < 1:
            raise ValueError('Oracle executed zero test cases: ' + name)
        total += count
    return total


def execute_oracle(metadata, repo_root, timeout=180):
    """Return fail-closed execution results and counts from managed runners."""
    result = {'exit_code': None, 'ok': False, 'error': None,
              'stdout': '', 'stderr': '', 'executed_tests': 0}
    try:
        root = Path(repo_root).resolve(strict=True)
        runner, names, files = _invocation(metadata, root)
        with tempfile.TemporaryDirectory(prefix='kdd-oracle-') as directory:
            temp = Path(directory)
            env = dict(os.environ)
            env.pop('NODE_OPTIONS', None)
            argv = _command(runner, names, root, temp)
            result.update(instrumented_argv=argv,
                          runtime_version=sys.version.split()[0] if runner == 'python-unittest' else None)
            completed = subprocess.run(argv, cwd=root,
                                       env=env, capture_output=True, text=True,
                                       encoding='utf-8', errors='replace', timeout=timeout)
            result.update(exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
            if completed.returncode:
                return result
            evidence = _evidence(runner, completed, temp)
            result['executed_tests'] = _verified_count(evidence, files, root)
            result.update(ok=True, evidence=evidence)
    except subprocess.TimeoutExpired:
        result['error'] = 'timeout'
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result.update(exit_code=1, error=str(exc))
    return result
