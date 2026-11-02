"""Verify an approved graph of KDD contracts and integration commands.

The caller must trust this runner, its interpreter and all executed code. This
is not a sandbox or a replacement for an independently approved quality policy.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys

import validate_contracts
import validate_test_commands


class InvalidGroup(ValueError):
    """Invalid group, reference or protected input."""


class GroupParser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidGroup(message)


def _git(root, *args):
    result = subprocess.run(['git', '--no-pager', *args], cwd=root,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=30, check=False)
    if result.returncode:
        raise InvalidGroup('Git operation failed')
    return result.stdout


def _ref(root, ref):
    git_root = Path(os.fsdecode(_git(root, 'rev-parse', '--show-toplevel').strip())).resolve()
    if os.path.normcase(str(git_root)) != os.path.normcase(str(root)):
        raise InvalidGroup('repo root must be the Git worktree root')
    object_format = _git(root, 'rev-parse', '--show-object-format').strip()
    sizes = {b'sha1': 40, b'sha256': 64}
    size = sizes.get(object_format)
    if not size or not re.fullmatch('[0-9a-fA-F]{%d}' % size, ref):
        raise InvalidGroup('approved reference must be a full native commit ID')
    ref = ref.lower()
    if _git(root, 'cat-file', '-t', ref).strip() != b'commit':
        raise InvalidGroup('approved reference must identify a commit')
    return ref


def _path(root, value):
    if (not isinstance(value, str) or not value or value.startswith('/')
            or any(ch in value for ch in '\\:\0\r\n')
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise InvalidGroup('invalid relative path')
    current = root
    for part in value.split('/'):
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise InvalidGroup('symbolic links and reparse points are not allowed')
    if not current.is_file():
        raise InvalidGroup('protected path must be a regular file')
    return current


def _normalized(data):
    try:
        text = data.decode('utf-8')
        if '\0' in text:
            return data
        return text.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
    except UnicodeDecodeError:
        return data


def _git_entry(root, ref, value):
    literal = ':(literal)' + value
    tree = _git(root, 'ls-tree', '-z', ref, '--', literal).split(b'\0')
    tree = [entry for entry in tree if entry]
    if len(tree) != 1 or b'\t' not in tree[0]:
        raise InvalidGroup('approved file is missing')
    header, name = tree[0].split(b'\t', 1)
    parts = header.split(b' ')
    if (len(parts) != 3 or parts[0] not in (b'100644', b'100755')
            or parts[1] != b'blob' or os.fsdecode(name) != value):
        raise InvalidGroup('approved path is not a regular file')
    index = [entry for entry in _git(root, 'ls-files', '--stage', '-z', '--', literal).split(b'\0') if entry]
    expected = parts[0] + b' ' + parts[2] + b' 0\t' + name
    if index != [expected]:
        raise InvalidGroup('index differs from approved file')
    return expected, _git(root, 'cat-file', 'blob', parts[2].decode('ascii'))


def _check_file(root, ref, value):
    path = _path(root, value)
    index_entry, baseline = _git_entry(root, ref, value)
    if _normalized(path.read_bytes()) != _normalized(baseline):
        raise InvalidGroup('working file differs from approved file')
    return path, (index_entry, baseline)


def _metadata(path):
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        raise InvalidGroup('missing group frontmatter')
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
    if closing is None:
        raise InvalidGroup('unterminated frontmatter')
    keys = []
    for line in lines[1:closing]:
        if line and not line[0].isspace() and not line.startswith('#') and ':' in line:
            keys.append(line.split(':', 1)[0].strip())
    if len(keys) != len(set(keys)):
        raise InvalidGroup('duplicate frontmatter key')
    metadata, _ = validate_contracts.parse_frontmatter(text)
    if not isinstance(metadata, dict):
        raise InvalidGroup('invalid frontmatter')
    return metadata


def _list(metadata, key, *, nonempty):
    value = metadata.get(key)
    if (not isinstance(value, list) or (nonempty and not value)
            or any(not isinstance(v, str) or not v for v in value)
            or len(value) != len(set(value))):
        raise InvalidGroup('invalid group list: ' + key)
    return value


def _group(metadata):
    if metadata.get('type') != 'Group Contract' or metadata.get('kind') != 'group':
        raise InvalidGroup('invalid group type')
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip()
           for key in ('title', 'description')):
        raise InvalidGroup('group requires OKF title and description')
    tags = _list(metadata, 'tags', nonempty=True)
    if any(tag != tag.lower() for tag in tags):
        raise InvalidGroup('group tags must be lowercase')
    children = _list(metadata, 'children', nonempty=True)
    tests = _list(metadata, 'integration_tests', nonempty=True)
    protected = _list(metadata, 'protected', nonempty=False)
    argv = _list(metadata, 'integration_argv', nonempty=True)
    if not all(path in argv[1:] for path in tests):
        raise InvalidGroup('each integration oracle must be named in argv')
    return children, tests, protected, argv


def _graph(root, ref, first):
    nodes, protected, ordered, visiting = {}, {}, [], set()

    def checked(value):
        if value in protected:
            return _path(root, value)
        path, evidence = _check_file(root, ref, value)
        protected[value] = evidence
        return path

    def visit(value):
        if value in visiting:
            raise InvalidGroup('group graph contains a cycle')
        if value in nodes:
            return
        visiting.add(value)
        path = checked(value)
        metadata = _metadata(path)
        if metadata.get('kind') == 'group':
            children, tests, extras, argv = _group(metadata)
            for item in tests + extras:
                checked(item)
            for child in children:
                visit(child)
            nodes[value] = ('integration', argv)
        else:
            if metadata.get('type') != 'Task Contract':
                raise InvalidGroup('child is not an atomic contract or group')
            findings = validate_contracts.validate_file(str(path), repo_root=str(root))
            if any(finding.level == 'ERROR' for finding in findings):
                raise InvalidGroup('invalid atomic contract')
            checked(metadata.get('tests'))
            command = metadata.get('test_command')
            if not isinstance(command, str) or not command.strip():
                raise InvalidGroup('atomic contract has no test command')
            nodes[value] = ('atomic', command)
        visiting.remove(value)
        ordered.append(value)

    visit(first)
    if nodes[first][0] != 'integration':
        raise InvalidGroup('root must be a group')
    return nodes, protected, ordered


def _check_all(root, protected):
    paths = sorted(protected)
    # Bounded batches avoid a subprocess per path without depending on shell
    # quoting or platform-specific command line length limits.
    pending, size = [], 0
    batches = []
    for value in paths:
        if pending and (len(pending) >= 32 or size + len(value) > 7000):
            batches.append(pending)
            pending, size = [], 0
        pending.append(value)
        size += len(value)
    if pending:
        batches.append(pending)
    for batch in batches:
        actual = [entry for entry in _git(root, 'ls-files', '--stage', '-z', '--',
                                         *(':(literal)' + value for value in batch)).split(b'\0') if entry]
        expected = [protected[value][0] for value in batch]
        if len(actual) != len(expected) or set(actual) != set(expected):
            raise InvalidGroup('index differs from approved files')
        for value in batch:
            if _normalized(_path(root, value).read_bytes()) != _normalized(protected[value][1]):
                raise InvalidGroup('working file differs from approved file')


def _atomic_command(command):
    posix = os.name != 'nt'
    tokens = shlex.split(command, posix=posix)
    if not posix:
        tokens = [validate_test_commands._strip_quotes(token) for token in tokens]
    if not tokens:
        raise InvalidGroup('empty atomic command')
    if re.fullmatch(r'python(?:3(?:\.\d+)?)?(?:\.exe)?', tokens[0], re.IGNORECASE):
        tokens[0] = sys.executable
    return shlex.join(tokens) if posix else subprocess.list2cmdline(tokens)


def _execute(root, nodes, protected, ordered, timeout, result):
    for name in ordered:
        stage, command = nodes[name]
        launched = False
        try:
            if stage == 'atomic':
                outcome = validate_test_commands.run_test_command(
                    _atomic_command(command), str(root), timeout, capture=True)
                timed_out = outcome.get('error') == 'timeout'
                ok = outcome.get('ok') is True
                execution_error = outcome.get('error') not in (None, 'timeout')
                launched = not execution_error
            else:
                argv = list(command)
                if argv[0].lower() in ('python', 'python3', 'python.exe'):
                    argv[0] = sys.executable
                process = validate_test_commands.run_process(
                    argv, cwd=str(root), timeout=timeout, capture_output=True, text=True,
                    encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONUTF8='1'))
                timed_out, execution_error = False, False
                launched = True
                ok = process.returncode == 0
        except subprocess.TimeoutExpired:
            timed_out, execution_error, ok = True, False, False
            launched = True
        except (OSError, ValueError):
            timed_out, execution_error, ok = False, True, False
        if launched:
            result['executed'].append(name)
        try:
            _check_all(root, protected)
        except (InvalidGroup, OSError, subprocess.SubprocessError):
            result.update(verdict='INVALID', stage='inputs-changed')
            return 2
        if timed_out:
            result.update(verdict='TIMEOUT', stage=stage)
            return 2
        if execution_error:
            result.update(verdict='INVALID', stage=stage)
            return 2
        if not ok:
            result.update(verdict='FAIL', stage=stage)
            return 1
    result.update(ok=True, verdict='PASS', stage='complete')
    return 0


def main():
    parser = GroupParser(description=__doc__)
    parser.add_argument('group')
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('--approved-ref', required=True)
    parser.add_argument('--timeout', type=float, default=120)
    try:
        args = parser.parse_args()
    except InvalidGroup as exc:
        print(json.dumps({'ok': False, 'verdict': 'INVALID', 'stage': 'preflight',
                          'approved_ref': '', 'executed': [], 'detail': str(exc)}, sort_keys=True))
        return 2
    result = {'ok': False, 'verdict': 'INVALID', 'stage': 'preflight',
              'approved_ref': args.approved_ref, 'executed': []}
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise InvalidGroup('timeout must be positive and finite')
        root = Path(args.repo_root).resolve(strict=True)
        ref = _ref(root, args.approved_ref)
        result['approved_ref'] = ref
        nodes, protected, ordered = _graph(root, ref, args.group)
        _check_all(root, protected)
        exit_code = _execute(root, nodes, protected, ordered, args.timeout, result)
    except (InvalidGroup, OSError, UnicodeError, subprocess.SubprocessError) as exc:
        result['detail'] = str(exc)
        exit_code = 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
