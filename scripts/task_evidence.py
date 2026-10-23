"""Run a recognized sealed oracle; this executor is trusted, not a sandbox."""
import hashlib
import os
import re
import shlex
import subprocess

from task_model import TaskError


def digest(content):
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def normalized(content):
    return content.replace('\r\n', '\n').replace('\r', '\n')


def invocation(metadata):
    tokens = shlex.split(metadata['test_command'], posix=os.name != 'nt')
    tokens = [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
    oracle = metadata['tests'].replace('\\', '/').removeprefix('./')
    if len(tokens) == 4 and re.fullmatch(r'python(?:3(?:\.\d+)?)?', tokens[0]):
        accepted = {oracle, oracle.removesuffix('.py').replace('/', '.')}
        if tokens[1:3] == ['-m', 'unittest'] and tokens[3] in accepted:
            return tokens, 'unittest'
    if tokens[:2] == ['node', '--test']:
        rest = [t for t in tokens[2:] if t != '--test-reporter=tap']
        if rest == [oracle]:
            return ['node', '--test', '--test-reporter=tap', oracle], 'node'
    raise TaskError('TASK_RUNNER: use python -m unittest or node --test with the exact sealed oracle')


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
        argv, runner = invocation(metadata)
        result = subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=timeout,
                                env=dict(os.environ, PYTHONUTF8='1'))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise TaskError('TASK_TESTS: oracle could not complete: ' + str(exc)) from exc
    count = passed_tests(runner, result.stdout, result.stderr)
    if result.returncode or not count:
        detail = (result.stdout + result.stderr)[-1500:]
        raise TaskError('TASK_TESTS: failing or zero recognized tests\n' + detail)
    return {'command': metadata['test_command'], 'runner': runner,
            'exit_code': result.returncode, 'passed_tests': count,
            'stdout': result.stdout, 'stderr': result.stderr,
            'output_sha256': digest(result.stdout + result.stderr)}
