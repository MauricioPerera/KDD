"""Run a recognized sealed oracle; this executor is trusted, not a sandbox."""
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess as _process_api

from task_model import TaskError, valid_sha


ACCEPTANCE_CHECKS = frozenset(('signature', 'dependencies', 'budget', 'forbids', 'invariants'))
ACCEPTANCE_INTERNAL = frozenset(('oracle-integrity', 'oracle-execution', 'perimeter'))


class _ContainedProcessAPI:
    """Keep the replaceable execution boundary and import-only audit support."""
    DEVNULL = _process_api.DEVNULL
    SubprocessError = _process_api.SubprocessError

    @staticmethod
    def run(argv, **options):
        # Historical audits load a frozen five-file bundle without executing
        # oracles. Only execution needs this additional runtime dependency.
        from process_tree import run
        return run(argv, **options)


subprocess = _ContainedProcessAPI()


def digest(content):
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def normalized(content):
    return content.replace('\r\n', '\n').replace('\r', '\n')


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('TASK_EVIDENCE: duplicate JSON key: ' + key)
        result[key] = value
    return result


def oracle_path(metadata):
    return metadata['tests'].replace('\\', '/').removeprefix('./')


def inventory(metadata):
    if 'oracle_files' not in metadata:
        return [oracle_path(metadata)]
    # The frozen legacy auditor does not include the inventory helper.
    from oracle_inventory import inventory_paths
    return inventory_paths(metadata, required=True)


def _runner_selection(tokens):
    if tokens[:2] == ['node', '--test']:
        names = [name for name in tokens[2:] if name != '--test-reporter=tap']
        if len(names) > 1 and len(tokens) - 2 - len(names) > 1:
            raise ValueError('duplicate TAP option')
        return ['node', '--test', '--test-reporter=tap', *names], 'node', names
    if (len(tokens) >= 4 and re.fullmatch(r'python(?:3(?:\.\d+)?)?', tokens[0])
            and tokens[1:3] == ['-m', 'unittest']):
        return tokens, 'unittest', tokens[3:]
    raise ValueError('use python -m unittest or node --test with explicit files')


def _selected_files(runner, names, approved):
    aliases = {name: {name} for name in approved}
    if runner == 'unittest':
        for name in approved:
            alias = name.removesuffix('.py').replace('/', '.')
            aliases.setdefault(alias, set()).add(name)
    files = []
    for name in names:
        matches = aliases.get(name, ())
        if name.startswith('-') or len(matches) != 1:
            raise ValueError('select only unambiguous approved oracle files')
        files.extend(matches)
    return files


def selection(metadata):
    try:
        tokens = shlex.split(metadata['test_command'], posix=os.name != 'nt')
        tokens = [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
        argv, runner, names = _runner_selection(tokens)
        if len(names) > 1:
            declared = 'python-unittest' if runner == 'unittest' else 'node-test'
            if 'oracle_files' not in metadata or metadata.get('test_runner') != declared:
                raise ValueError('multiple files require oracle_files and a matching test_runner')
        files = _selected_files(runner, names, inventory(metadata))
        if oracle_path(metadata) not in files or len(files) != len(set(files)):
            raise ValueError('include the primary oracle exactly once and avoid duplicate files')
        return argv, runner, files
    except ValueError as exc:
        raise TaskError('TASK_RUNNER: ' + str(exc)) from exc


def invocation(metadata):
    argv, runner, _ = selection(metadata)
    return argv, runner


def passed_tests(runner, stdout, stderr):
    if runner == 'unittest':
        match = re.search(r'Ran (\d+) tests? in [^\n]+\n\nOK(?: \(([^\n]*)\))?\s*\Z', normalized(stderr))
        if not match:
            return 0
        counts = re.findall(r'(?:skipped|expected failures)=(\d+)', match[2] or '')
        return max(0, int(match[1]) - sum(map(int, counts)))
    match = re.search(r'^# pass (\d+)\r?$', stdout, re.MULTILINE)
    failed = re.search(r'^# fail (\d+)\r?$', stdout, re.MULTILINE)
    if match and failed and int(failed[1]) == 0:
        return int(match[1])
    return 0


def execute(metadata, root, timeout=120):
    try:
        # The frozen task auditor imports this module without its live runners.
        try:
            from oracle_execution import execute_task_oracle
        except ImportError as error:
            if error.name != 'oracle_execution':
                raise
            # An isolated suite can load this file by path while only the
            # repository root is available to normal package imports.
            from scripts.oracle_execution import execute_task_oracle
        argv, runner, files = selection(metadata)
        instrument = 'python-unittest' if runner == 'unittest' else 'node-test'
        run = partial(subprocess.run, stdin=subprocess.DEVNULL)
        result = execute_task_oracle(instrument, argv[0], files, root, timeout, run)
    except (OSError, ValueError, ImportError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise TaskError('TASK_TESTS: oracle could not complete: ' + str(exc)) from exc
    output = result['stdout'] + result['stderr']
    if not result['ok']:
        raise TaskError('TASK_TESTS: failing or zero recognized tests\n' + output[-1500:])
    return _receipt(metadata, root, runner, files, result)


def _receipt(metadata, root, runner, files, result):
    rows = result['evidence']['files']
    recorded = {name: rows[str((Path(root) / name).resolve())] for name in files}
    return {'schema_version': 2, 'command': metadata['test_command'], 'runner': runner,
            'exit_code': result['exit_code'], 'passed_tests': result['executed_tests'],
            'stdout': result['stdout'], 'stderr': result['stderr'],
            'oracle_results': recorded, 'output_sha256': digest(result['stdout'] + result['stderr'])}


def _pass_receipt(root, attempt):
    ids = {Path(name).relative_to(root).as_posix(): sorted(cases)
           for name, cases in attempt['runner_evidence']['case_ids'].items()}
    inventory = json.dumps(ids, sort_keys=True, separators=(',', ':'))
    return {'iteration': attempt['iteration'], 'executed': attempt['executed_tests'],
            'case_ids_sha256': digest(inventory), 'output_sha256': attempt['output_sha256']}


def acceptance_receipt(metadata, root, matrix, identity, contract):
    """Reuse the second primary run and retain compact evidence for each row."""
    checks, primaries = [], {}
    for item in matrix['contracts']:
        for row in item['obligations']:
            name = row['obligation']
            if name in ('oracle-integrity', 'perimeter'):
                continue
            checks.append({'contract': item['path'], 'obligation': name,
                           'passes': [_pass_receipt(root, p) for p in row['evidence']]})
            if name == 'oracle-execution':
                primaries[item['path']] = row['evidence'][1]
    primary = primaries[contract]
    outcome = {**primary, 'evidence': primary['runner_evidence']}
    _, runner, files = selection(metadata)
    report = _receipt(metadata, root, runner, files, outcome)
    report['acceptance'] = dict(identity, checks=checks)
    return report


def _acceptance_pass(attempt, iteration):
    keys = {'iteration', 'executed', 'case_ids_sha256', 'output_sha256'}
    if not isinstance(attempt, dict) or attempt.keys() != keys:
        return False
    return (type(attempt['iteration']) is int and attempt['iteration'] == iteration
            and type(attempt['executed']) is int and attempt['executed'] > 0
            and all(valid_sha(attempt[field]) and len(attempt[field]) == 64
                    for field in ('case_ids_sha256', 'output_sha256')))


def _accepted_rows(checks):
    if not isinstance(checks, list):
        raise TaskError('TASK_ACCEPTANCE: checks must be a list')
    rows = {}
    for row in checks:
        if not isinstance(row, dict) or set(row) != {'contract', 'obligation', 'passes'}:
            raise TaskError('TASK_ACCEPTANCE: invalid obligation record')
        key = row['contract'], row['obligation']
        if not all(isinstance(value, str) for value in key) or key in rows:
            raise TaskError('TASK_ACCEPTANCE: invalid or repeated obligation')
        passes = row['passes']
        if not isinstance(passes, list) or len(passes) != 2 or not all(
                _acceptance_pass(attempt, index) for index, attempt in enumerate(passes, 1)):
            raise TaskError('TASK_ACCEPTANCE: expected two complete passes for ' + ' / '.join(key))
        if any(passes[0][name] != passes[1][name] for name in ('executed', 'case_ids_sha256')):
            raise TaskError('TASK_ACCEPTANCE: case inventory differs between passes')
        rows[key] = passes[1]
    return rows


def check_acceptance_receipt(report, identity, expected, contract):
    accepted = report.get('acceptance')
    if report['schema_version'] != 2 or not isinstance(accepted, dict) or (
            set(accepted) != set(identity) | {'checks'}
            or any(accepted[field] != value for field, value in identity.items())):
        raise TaskError('TASK_ACCEPTANCE: absent receipt or identity differs from Git')
    rows = _accepted_rows(accepted['checks'])
    if rows.keys() != expected:
        raise TaskError('TASK_ACCEPTANCE: receipt differs from approved obligation inventory')
    primary = rows[contract, 'oracle-execution']
    if (primary['executed'] != report['passed_tests']
            or primary['output_sha256'] != report['output_sha256']):
        raise TaskError('TASK_ACCEPTANCE: primary result differs from second acceptance pass')
