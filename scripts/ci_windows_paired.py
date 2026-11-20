"""Compare two pinned checkouts using the same isolated Windows suite profile."""

import argparse
import hashlib
from itertools import combinations
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time


ROLES = ('reference', 'candidate')
RUNTIME_FILES = (
    'trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
    'validate_contracts.py', 'process_tree.py', 'execution_profile.py',
)
SHA = re.compile(r'[0-9a-f]{40}')
DIGEST = re.compile(r'[0-9a-f]{64}')


class ProbeError(ValueError):
    """A diagnostic which prevents publishing a successful comparison."""

    def __init__(self, code, message):
        super().__init__(code + ': ' + message)


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('duplicate JSON key')
    return result


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)


def _write(path, payload):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _arm(raw):
    fields = {'checkout', 'commit', 'tree', 'ids_sha256'}
    if (not isinstance(raw, dict) or raw.keys() != fields
            or any(not isinstance(value, str) for value in raw.values())
            or not Path(raw['checkout']).is_absolute()
            or any(not SHA.fullmatch(raw[field]) for field in ('commit', 'tree'))
            or not DIGEST.fullmatch(raw['ids_sha256'])):
        raise ValueError('invalid arm identity')
    return dict(raw, checkout=Path(raw['checkout']).resolve(strict=True))


def _load_plan(path):
    try:
        plan = _json(path)
        if (not isinstance(plan, dict)
                or plan.keys() != {'schema_version', 'order', 'runtime_ref', 'bundle', 'arms'}
                or type(plan['schema_version']) is not int or plan['schema_version'] != 1
                or plan['order'] not in (list(ROLES), list(reversed(ROLES)))
                or not isinstance(plan['runtime_ref'], str) or not SHA.fullmatch(plan['runtime_ref'])
                or not isinstance(plan['bundle'], str) or not Path(plan['bundle']).is_absolute()
                or not isinstance(plan['arms'], dict) or plan['arms'].keys() != set(ROLES)):
            raise ValueError('invalid plan schema, order or runtime reference')
        plan['arms'] = {role: _arm(raw) for role, raw in plan['arms'].items()}
        plan['bundle'] = Path(plan['bundle']).resolve(strict=True)
    except (OSError, ValueError) as error:
        raise ProbeError('PAIRED_PLAN', str(error)) from error
    return plan


def _require_disjoint(plan, output):
    checkouts = [arm['checkout'] for arm in plan['arms'].values()]
    for left, right in combinations([*checkouts, plan['bundle'], output], 2):
        if left.is_relative_to(right) or right.is_relative_to(left):
            raise ProbeError('PAIRED_OUTPUT', 'checkouts, bundle and output must be disjoint')


def _git(git, root, *args):
    return subprocess.check_output(
        [git, '--no-replace-objects', '-C', str(root), *args],
        cwd=Path(git).parent, stderr=subprocess.PIPE, timeout=30,
    )


def _check_checkout(git, arm):
    root = arm['checkout']
    try:
        top = Path(os.fsdecode(_git(git, root, 'rev-parse', '--show-toplevel').rstrip()))
        head = _git(git, root, 'rev-parse', '--verify', 'HEAD').strip().decode('ascii')
        tree = _git(git, root, 'rev-parse', '--verify', 'HEAD^{tree}').strip().decode('ascii')
        status = _git(git, root, 'status', '--porcelain=v1', '--untracked-files=all')
        if top.resolve() == root and head == arm['commit'] and tree == arm['tree'] and not status:
            return
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise ProbeError('PAIRED_CHECKOUT', str(error)) from error
    raise ProbeError('PAIRED_CHECKOUT', 'checkout identity or worktree changed: ' + str(root))


def _check_runtime(git, plan):
    bundle, ref = plan['bundle'], plan['runtime_ref']
    root = plan['arms']['reference']['checkout']
    try:
        manifest = _json(bundle / 'manifest.json')
        if (manifest['version'] != 1 or manifest['trusted_ref'] != ref
                or manifest['files'].keys() != set(RUNTIME_FILES)
                or _git(git, root, 'cat-file', '-t', ref).strip() != b'commit'):
            raise ValueError('bundle identity does not match the pinned runtime')
        for name in RUNTIME_FILES:
            original = _git(git, root, 'show', ref + ':scripts/' + name)
            digest = hashlib.sha256(original).hexdigest()
            path = bundle / name
            if path.is_symlink() or manifest['files'][name] != digest or path.read_bytes() != original:
                raise ValueError('bundle does not match Git: ' + name)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError) as error:
        raise ProbeError('PAIRED_RUNTIME', str(error)) from error


def _child_env(root):
    env = {name: value for name, value in os.environ.items()
           if not name.upper().startswith('COVERAGE_')}
    temp = root / 'tmp'
    temp.mkdir()
    env.update(TMP=str(temp), TEMP=str(temp), TMPDIR=str(temp), KDD_SKIP_INIT_POST_APPLY_SUITE='1')
    return env


def _startup(git, folder, env):
    result = {}
    for label, executable in (('git', git), ('python', sys.executable)):
        samples = []
        for _ in range(7):
            start = time.perf_counter()
            version = subprocess.check_output(
                [executable, '--version'], cwd=folder, env=env, stderr=subprocess.STDOUT, timeout=30,
            )
            samples.append(time.perf_counter() - start)
        result[label] = {'version': version.decode('ascii').strip(),
                         'samples_seconds': samples, 'median_seconds': statistics.median(samples)}
    return result


def _inventory(data, name, digest):
    values = data.get(name)
    if (not isinstance(values, list) or not values
            or any(not isinstance(value, str) or not value or '\n' in value or '\r' in value for value in values)
            or len(values) != len(set(values))):
        raise ProbeError('PAIRED_INVENTORY', 'invalid ' + name)
    actual = hashlib.sha256(('\n'.join(sorted(values)) + '\n').encode('utf-8')).hexdigest()
    if actual != digest:
        raise ProbeError('PAIRED_INVENTORY', 'digest mismatch for ' + name)
    return set(values)


def _suite(plan, arm, folder, env, number):
    report = folder / f'suite-{number}.json'
    argv = [sys.executable, '-I', '-B', str(plan['bundle'] / 'trusted_ci.py'), 'suite',
            '--repo-root', str(arm['checkout']), '--start-directory', 'tests',
            '--pattern', 'test_*.py', '--workers', '6', '--report-json', str(report)]
    with (folder / f'suite-{number}.log').open('xb') as log:
        started_ns, start = time.time_ns(), time.perf_counter()
        with subprocess.Popen(argv, cwd=arm['checkout'], env=env, stdout=log, stderr=subprocess.STDOUT) as child:
            pid, code = child.pid, child.wait()
        seconds, ended_ns = time.perf_counter() - start, time.time_ns()
    _write(folder / f'suite-{number}-process.json',
           dict(pid=pid, started_ns=str(started_ns), ended_ns=str(ended_ns), exit_code=code,
                duration_seconds=seconds))
    if code != 0:
        raise ProbeError('PAIRED_SUITE', str(report) + ' failed (exit ' + str(code) + ')')
    try:
        data = _json(report)
        if (data.get('ok') is not True or data.get('workers') != 6
                or data.get('trusted_runtime_ref') != plan['runtime_ref']):
            raise ValueError('suite failed or attested a different profile')
    except (OSError, ValueError, AttributeError) as error:
        raise ProbeError('PAIRED_SUITE', str(error)) from error
    if data.get('fixture_omitted_ids') != []:
        raise ProbeError('PAIRED_INVENTORY', 'suite omitted fixture cases')
    ids = _inventory(data, 'expected_ids', arm['ids_sha256'])
    if ids != _inventory(data, 'executed_ids', arm['ids_sha256']):
        raise ProbeError('PAIRED_INVENTORY', 'expected and executed IDs differ')
    return ids, dict(number=number, duration_seconds=seconds, ids_sha256=arm['ids_sha256'],
                     coverage=number == 1)


def _coverage(arm, folder, env, command):
    root, path = arm['checkout'], folder / 'coverage'
    cli = [sys.executable, '-I', '-B', str(root / 'scripts/ci_coverage.py'), command,
           '--repo-root', str(root), '--output', str(path)]
    identity = dict(head_sha=arm['commit'], run_id=os.getenv('GITHUB_RUN_ID', 'local-pair'),
                    attempt=os.getenv('GITHUB_RUN_ATTEMPT', '1'),
                    platform='windows-latest' if os.name == 'nt' else 'ubuntu-local')
    if command == 'report':
        for name, value in identity.items():
            cli.extend(('--' + name.replace('_', '-'), value))
    try:
        with (folder / f'coverage-{command}.log').open('xb') as log:
            subprocess.run(cli, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                           timeout=180, check=True)
        if command == 'prepare':
            if (path / 'coverage.ini').is_file():
                return
            raise ValueError('coverage config absent')
        coverage = _json(path / 'coverage.json')
        observed = coverage['kdd']
        totals = coverage['totals']
        if (any(observed.get(key) != value for key, value in identity.items())
                or observed.get('suite_pass') != 1 or observed.get('fragments', 0) < 1
                or coverage['meta'].get('branch_coverage') is not True
                or not all(totals[name] > 0 for name in ('num_statements', 'num_branches'))):
            raise ValueError('coverage lacks first-pass identity or branch data')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError) as error:
        raise ProbeError('PAIRED_COVERAGE', str(error)) from error


def _run_arm(git, plan, role, output):
    arm = plan['arms'][role]
    folder = output / role
    folder.mkdir()
    _check_checkout(git, arm)
    env = _child_env(folder)
    startup = _startup(git, folder, env)
    _write(folder / 'startup.json', startup)
    _coverage(arm, folder, env, 'prepare')
    first_env = dict(env, COVERAGE_PROCESS_START=str(folder / 'coverage' / 'coverage.ini'))
    first_ids, first = _suite(plan, arm, folder, first_env, 1)
    fragments = {path.name for path in (folder / 'coverage').glob('.coverage.*')}
    second_ids, second = _suite(plan, arm, folder, env, 2)
    if first_ids != second_ids:
        raise ProbeError('PAIRED_INVENTORY', 'suite passes disagree')
    if fragments != {path.name for path in (folder / 'coverage').glob('.coverage.*')}:
        raise ProbeError('PAIRED_COVERAGE', 'second pass created or removed coverage fragments')
    _check_checkout(git, arm)
    _coverage(arm, folder, env, 'report')
    return first_ids, dict(commit=arm['commit'], tree=arm['tree'], passes=[first, second],
                           startup=startup)


def _compare(plan, output):
    _require_disjoint(plan, output)
    if os.path.lexists(output):
        raise ProbeError('PAIRED_OUTPUT', 'output must be new')
    executable = shutil.which('git', path=os.pathsep.join(
        folder for folder in os.get_exec_path() if Path(folder).is_absolute()
    ))
    if executable is None:
        raise ProbeError('PAIRED_CHECKOUT', 'Git is required')
    git = str(Path(executable).resolve(strict=True))
    if any(Path(git).is_relative_to(arm['checkout']) for arm in plan['arms'].values()):
        raise ProbeError('PAIRED_CHECKOUT', 'Git must be outside the measured checkouts')
    for arm in plan['arms'].values():
        _check_checkout(git, arm)
    _check_runtime(git, plan)
    output.mkdir(parents=True, exist_ok=False)
    inventories, summaries = {}, {}
    for role in plan['order']:
        inventories[role], summaries[role] = _run_arm(git, plan, role, output)
    if not inventories['reference'] <= inventories['candidate']:
        raise ProbeError('PAIRED_INVENTORY', 'candidate dropped reference test IDs')
    for arm in plan['arms'].values():
        _check_checkout(git, arm)
    _check_runtime(git, plan)
    _write(output / 'comparison.json', dict(schema_version=1, order=plan['order'],
                                           runtime_ref=plan['runtime_ref'], arms=summaries))


def main(argv=None):
    """Execute a paired plan and publish results only after complete checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise ProbeError('PAIRED_OUTPUT', 'output must be new')
        _compare(_load_plan(args.plan), args.output.resolve())
    except ProbeError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('PAIRED_EXECUTION: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
