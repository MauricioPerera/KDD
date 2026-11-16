"""Replay the complete init command for the reviewed PR 196 tree."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


SOURCE_SHA = '088225c2ff241b773353825f45c9e63a57861173'
SOURCE_TREE = '71e569b721d4f7785c3b8159a8befcdc06eaceed'
RUNTIME_SHA = '74d357f7099651b9b39dc8088f725183a672ec94'
BASELINE_SHA = '47afa8d45e6139e4ce8939fd4e8f07d65f85f7cb'
INIT_COMMAND = 'python -m unittest tests/test_init_project.py'

RUNTIME_FILES = ('trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
                 'validate_contracts.py', 'process_tree.py', 'execution_profile.py')
MANAGED_FILES = ('oracle_execution.py', 'oracle_inventory.py',
                 'unittest_oracle_runner.py', 'node_oracle_reporter.mjs')
MAX_OUTPUT = 192 * 1024
OUTPUT = 'kdd-postinit-pr196-replay.json'
MARKER = 'kdd-postinit-project.json'
COLLECTED = 'kdd-postinit-progress.json'
NUMBER = re.compile(r'[1-9][0-9]{0,19}')
OID = re.compile(r'[0-9a-f]{40}')
MODULE = re.compile(r'(?:[A-Za-z_][A-Za-z0-9_]*\.)*test_[A-Za-z0-9_]+')

# Load the verified bundle in a separate interpreter so environment, imports
# and tempfile caches belong to this attempt.
RUN_ENTRY = """\
import json
from pathlib import Path
import sys
import time

bundle, command, timeout = sys.argv[1:]
sys.path.insert(0, bundle)
from trusted_ci import _runtime
from validate_test_commands import run_test_command

root = Path.cwd().resolve()
_runtime(root)
started = time.time_ns()
start = time.perf_counter()
result = run_test_command(command, str(root), float(timeout), capture=True,
                          trusted_bundle=Path(bundle))
duration = time.perf_counter() - start
print(json.dumps(dict(result=result, duration_seconds=duration, started=started,
                      stopped=time.time_ns()), allow_nan=False))
"""


def _git(source, *args):
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(source), *args],
                                   stderr=subprocess.PIPE, timeout=30)


def _revision(source):
    return _git(source, 'rev-parse', 'HEAD', 'HEAD^{tree}').decode('ascii').splitlines()


def check_checkout(source, sha, tree):
    if _revision(source) != [sha, tree] or _git(source, 'status', '--porcelain'):
        raise ValueError('checkout differs from the reviewed commit and tree')


def _regular(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError('expected an unlinked regular evidence file')
    return info


def _read_json(path):
    if _regular(path).st_size > MAX_OUTPUT:
        raise ValueError('evidence file exceeds its byte limit')
    with path.open('rb') as stream:
        raw = stream.read(MAX_OUTPUT + 1)
    if len(raw) > MAX_OUTPUT:
        raise ValueError('evidence file exceeds its byte limit')
    return json.loads(raw)


def _runtime_files(source, runtime):
    managed = _git(source, 'ls-tree', '--name-only', runtime, '--', 'scripts/oracle_execution.py')
    return RUNTIME_FILES + MANAGED_FILES if managed.strip() else RUNTIME_FILES


def _check_member(source, bundle, runtime, name):
    path = 'scripts/' + name
    entry = _git(source, 'ls-tree', runtime, '--', path)
    if not entry.startswith((b'100644 blob ', b'100755 blob ')):
        raise ValueError('reviewed runtime member is not a regular Git blob')
    target = bundle / name
    _regular(target)
    blob = _git(source, 'show', runtime + ':' + path)
    if target.read_bytes() != blob:
        raise ValueError('runtime member differs from reviewed Git bytes: ' + name)
    return hashlib.sha256(blob).hexdigest()


def _check_bundle(source, bundle, runtime):
    if (not OID.fullmatch(runtime) or bundle.is_relative_to(source)
            or _git(source, 'cat-file', '-t', runtime).strip() != b'commit'):
        raise ValueError('runtime requires an external bundle at a reviewed commit')
    names = _runtime_files(source, runtime)
    if {entry.name for entry in bundle.iterdir()} != set(names) | {'manifest.json'}:
        raise ValueError('runtime bundle members differ from the reviewed inventory')
    hashes = {name: _check_member(source, bundle, runtime, name) for name in names}
    if _read_json(bundle / 'manifest.json') != dict(version=1, trusted_ref=runtime, files=hashes):
        raise ValueError('runtime manifest differs from the reviewed inventory')


def _environment(source, env):
    source_sha, source_tree = _revision(source)
    probe_sha = env['GITHUB_SHA']
    run_id, attempt = env['GITHUB_RUN_ID'], env['GITHUB_RUN_ATTEMPT']
    if not (NUMBER.fullmatch(run_id) and NUMBER.fullmatch(attempt) and OID.fullmatch(probe_sha)):
        raise ValueError('invalid replay run identity')
    runner = Path(env['RUNNER_TEMP']).resolve(strict=True)
    private = Path(env['TMPDIR']).resolve(strict=True)
    if (runner.is_relative_to(source) or private.parent != runner
            or not private.name.startswith('kdd-native-tests-')):
        raise ValueError('replay requires a private native temporary directory outside the checkout')
    child = dict(env, GITHUB_SHA=source_sha, GITHUB_WORKSPACE=str(source),
                 KDD_OBSERVE_POSTINIT='1', TEMP=str(private), TMP=str(private), TMPDIR=str(private))
    child.pop('KDD_SKIP_INIT_POST_APPLY_SUITE', None)
    metadata = dict(source_sha=source_sha, source_tree=source_tree, probe_sha=probe_sha,
                    run_id=run_id, run_attempt=attempt, runtime_sha=env['KDD_TRUSTED_RUNTIME_REF'])
    return child, metadata, runner


def _run(source, bundle, environment, timeout):
    proc = subprocess.run([sys.executable, '-I', '-B', '-c', RUN_ENTRY, str(bundle),
                           INIT_COMMAND, str(timeout)], cwd=source, env=environment,
                          capture_output=True, timeout=timeout+60, check=True)
    return json.loads(proc.stdout)


def _init_profile(stdout):
    summaries = []
    for line in stdout.splitlines():
        if line.startswith('KDD_POST_INIT_PROFILE {"kind": "summary"'):
            summaries.append(json.loads(line.removeprefix('KDD_POST_INIT_PROFILE ')))
    if len(summaries) != 1:
        return None
    row = summaries[0]
    if (row.get('platform') != 'win32' or row.get('workers') != 10
            or row.get('tests_run') != 2374 or row.get('expected_count') != 2374
            or row.get('fixture_omitted_count') != 0):
        return None
    return dict(cases=2374, workers=10)


def _expected_observation(metadata):
    return dict(schema_version=1, run_id=metadata['run_id'], run_attempt=metadata['run_attempt'],
                head_sha=metadata['source_sha'], trusted_runtime_ref=metadata['runtime_sha'],
                platform=sys.platform)


def _valid_module(name):
    return isinstance(name, str) and len(name) <= 160 and MODULE.fullmatch(name) is not None


def _valid_row(row):
    if not isinstance(row, dict) or row.keys() != {'index', 'name', 'cases', 'phase', 'duration_seconds'}:
        return False
    name, duration = row['name'], row['duration_seconds']
    if (type(row['index']) is not int or not 0 <= row['index'] <= 999
            or type(row['cases']) is not int or row['cases'] < 1
            or not _valid_module(name)):
        return False
    if row['phase'] == 'incomplete':
        return duration is None
    return (row['phase'] == 'completed' and type(duration) in (int, float)
            and math.isfinite(duration) and duration >= 0)


def _validated_observation(raw, expected):
    if not isinstance(raw, dict):
        raise ValueError('collector output must be an object')
    data = dict(raw)
    modules = data.pop('modules')
    state = data.pop('state')
    if data != expected or state not in ('partial', 'not_found', 'inconclusive'):
        raise ValueError('invalid collector identity or state')
    if not isinstance(modules, list) or len(modules) > 512 or bool(modules) != (state == 'partial'):
        raise ValueError('invalid collector module list')
    if not all(_valid_row(row) for row in modules):
        raise ValueError('invalid collector module record')
    if any(len({row[key] for row in modules}) != len(modules) for key in ('index', 'name')):
        raise ValueError('duplicate collector module record')
    return dict(expected, state=state, modules=modules)


def _observation(source, runner, environment, metadata):
    expected = _expected_observation(metadata)
    path = runner / COLLECTED
    try:
        if os.path.lexists(path):
            raise ValueError('collector output already exists')
        subprocess.run([sys.executable, '-I', '-B', str(source/'scripts/postinit_timeout_observation.py'),
                        '--ci-output'], cwd=source, env=environment, capture_output=True,
                       timeout=45, check=True)
        return _validated_observation(_read_json(path), expected)
    except (KeyError, OSError, ValueError, TypeError, RecursionError, subprocess.SubprocessError):
        return dict(expected, state='inconclusive', modules=[])


def _handoff(environment, receipt, observation):
    if observation['state'] != 'partial':
        return None
    try:
        mark = _regular(Path(environment['TMPDIR']) / MARKER).st_mtime_ns
    except (OSError, ValueError):
        return None
    offset = (mark - receipt['started']) / 1e9
    if mark <= receipt['stopped'] and 0 <= offset <= receipt['duration_seconds']:
        return offset
    return None


def _outcome(receipt):
    return {key: receipt['result'][key] for key in ('ok', 'error', 'exit_code')}


def replay(source, bundle, env, timeout=600):
    source = Path(source).resolve(strict=True)
    bundle = Path(bundle).resolve(strict=True)
    environment, metadata, runner = _environment(source, env)
    _check_bundle(source, bundle, metadata['runtime_sha'])
    receipt = _run(source, bundle, environment, timeout)
    raw = _outcome(receipt)
    result = dict(schema_version=1, **metadata, duration_seconds=receipt['duration_seconds'],
                  outcome=raw, observation=None, profile=None, handoff_seconds=None)
    if raw['error'] == 'timeout':
        result['observation'] = _observation(source, runner, environment, metadata)
        result['handoff_seconds'] = _handoff(environment, receipt, result['observation'])
        return 124, result
    if raw['ok']:
        try:
            result['profile'] = _init_profile(receipt['result'].get('stdout', ''))
        except ValueError:
            result['profile'] = None
        return (0 if result['profile'] else 2), result
    return raw['exit_code'] or 1, result


def _write_report(path, record):
    data = (json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
    if len(data) > MAX_OUTPUT:
        raise ValueError('replay summary exceeds its byte limit')
    with path.open('xb') as stream:
        stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = args.source.resolve(strict=True)
        check_checkout(source, SOURCE_SHA, SOURCE_TREE)
        output = Path(os.environ['RUNNER_TEMP']).resolve(strict=True) / OUTPUT
        if os.path.lexists(output):
            raise ValueError('replay summary already exists')
        if os.environ['KDD_TRUSTED_RUNTIME_REF'] != RUNTIME_SHA:
            raise ValueError('runtime differs from the reviewed pin')
        env = dict(os.environ, KDD_APPROVED_BASELINE_REF=BASELINE_SHA,
                   KDD_ACCEPTANCE_APPROVED_REF=BASELINE_SHA)
        code, result = replay(source, args.bundle, env)
        _write_report(output, result)
        print('Init command measured in {:.2f} s (exit {})'.format(result['duration_seconds'], code))
        return code
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print('POSTINIT_REPLAY: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
