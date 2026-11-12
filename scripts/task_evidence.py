"""Run a recognized sealed oracle; this executor is trusted, not a sandbox."""
from functools import partial
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess as _process_api

from task_model import TaskError


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


def invocation(metadata):
    tokens = shlex.split(metadata['test_command'], posix=os.name != 'nt')
    tokens = [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
    oracle = oracle_path(metadata)
    if len(tokens) == 4 and re.fullmatch(r'python(?:3(?:\.\d+)?)?', tokens[0]):
        accepted = {oracle, oracle.removesuffix('.py').replace('/', '.')}
        if tokens[1:3] == ['-m', 'unittest'] and tokens[3] in accepted:
            return tokens, 'unittest'
    if tokens[:2] == ['node', '--test']:
        rest = [t for t in tokens[2:] if t != '--test-reporter=tap']
        if rest == [oracle]:
            return ['node', '--test', '--test-reporter=tap', oracle], 'node'
    raise TaskError('TASK_RUNNER: use python -m unittest or node --test with the exact sealed oracle')


def oracle_path(metadata):
    return metadata['tests'].replace('\\', '/').removeprefix('./')


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
        from oracle_execution import execute_task_oracle
        argv, runner = invocation(metadata)
        oracle = oracle_path(metadata)
        instrument = 'python-unittest' if runner == 'unittest' else 'node-test'
        run = partial(subprocess.run, stdin=subprocess.DEVNULL)
        result = execute_task_oracle(instrument, argv[0], oracle, root, timeout, run)
    except (OSError, ValueError, ImportError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise TaskError('TASK_TESTS: oracle could not complete: ' + str(exc)) from exc
    output = result['stdout'] + result['stderr']
    if not result['ok']:
        raise TaskError('TASK_TESTS: failing or zero recognized tests\n' + output[-1500:])
    recorded = result['evidence']['files'][str((Path(root) / oracle).resolve())]
    return {'schema_version': 2, 'command': metadata['test_command'], 'runner': runner,
            'exit_code': result['exit_code'], 'passed_tests': result['executed_tests'],
            'stdout': result['stdout'], 'stderr': result['stderr'],
            'oracle_results': {oracle: recorded}, 'output_sha256': digest(output)}
