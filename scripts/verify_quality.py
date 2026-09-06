"""Run an approved project's quality checks with fail-closed integrity gates.

The caller-selected commit and this executor are trusted. Commands are not
sandboxed; kind labels describe reviewed checks, not their oracle strength.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys


class Rejected(ValueError):
    """An approval condition was not satisfied."""


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args],
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise Rejected('Git operation failed: ' + result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def safe_path(root, value):
    if not isinstance(value, str) or not value or any(c in value for c in '\\\x00:*?[]'):
        raise Rejected('Invalid exact relative path: ' + repr(value))
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise Rejected('Invalid relative path: ' + repr(value))
    local = root.joinpath(*path.parts)
    if not local.resolve().is_relative_to(root):
        raise Rejected('Path escapes repository: ' + value)
    return local


def strings(value, label, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise Rejected('Expected list: ' + label)
    if any(not isinstance(item, str) or not item.strip() or '\x00' in item for item in value):
        raise Rejected('Expected nonempty strings: ' + label)
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def validate_policy(root, data):
    fields = {'protected', 'implementation', 'pm', 'required_kinds', 'checks'}
    if not isinstance(data, dict) or set(data) != fields:
        raise Rejected('Policy fields must be: ' + ', '.join(sorted(fields)))
    for field in ('protected', 'implementation', 'pm'):
        for name in strings(data[field], field, field == 'protected'):
            safe_path(root, name)
    required = strings(data['required_kinds'], 'required_kinds', True)
    if not {'functional', 'adversarial'}.issubset(required):
        raise Rejected('functional and adversarial kinds are required')
    if not isinstance(data['checks'], list) or not data['checks']:
        raise Rejected('checks must be a nonempty list')
    names, kinds = set(), set()
    for check in data['checks']:
        if not isinstance(check, dict) or set(check) != {'name', 'kind', 'argv', 'timeout'}:
            raise Rejected('Invalid check schema')
        strings([check['name'], check['kind']], 'check name/kind', True)
        if check['name'] in names:
            raise Rejected('Duplicate check name: ' + check['name'])
        names.add(check['name'])
        kinds.add(check['kind'])
        strings(check['argv'], 'argv', True)
        if type(check['timeout']) is not int or not 0 < check['timeout'] <= 3600:
            raise Rejected('timeout must be an integer in 1..3600')
    if not set(required).issubset(kinds):
        raise Rejected('Required kind has no check')
    return data


def normalized(content):
    return content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def changed_paths(root, commit):
    names = set()
    commands = [
        ('diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', commit, '--'),
        ('diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', '--cached', commit, '--'),
        ('diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', '--'),
        ('ls-files', '--others', '--exclude-standard', '-z'),
    ]
    for command in commands:
        names.update(p.decode('utf-8') for p in git(root, *command).split(b'\x00') if p)
    return names


def integrity(root, commit, policy_path, policy, approved):
    for field in ('protected', 'implementation', 'pm'):
        for name in policy[field]:
            safe_path(root, name)
    for name, content in approved.items():
        path = safe_path(root, name)
        if not path.is_file() or path.is_symlink():
            raise Rejected('Protected file missing or symlink: ' + name)
        if normalized(path.read_bytes()) != normalized(content):
            raise Rejected('Protected file changed: ' + name)
        # Check index too: staged tampering cannot hide behind restored work files.
        index = git(root, 'show', ':' + name)
        if normalized(index) != normalized(content):
            raise Rejected('Protected index changed: ' + name)
    allowed = set(policy['implementation']) | set(policy['pm'])
    for name in changed_paths(root, commit):
        safe_path(root, name)
        if name not in allowed and name not in approved:
            raise Rejected('Outside approved perimeter: ' + name)


def approve(root, policy_path, reference):
    root = root.resolve(strict=True)
    actual = Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if actual != root:
        raise Rejected('repo-root must be the Git repository root')
    safe_path(root, policy_path)
    commit = git(root, 'rev-parse', '--verify', '--end-of-options', reference + '^{commit}').decode().strip()
    raw = git(root, 'show', commit + ':' + policy_path)
    policy = validate_policy(root, json.loads(raw, object_pairs_hook=unique_object))
    approved = {policy_path: raw}
    for name in policy['protected']:
        approved[name] = git(root, 'show', commit + ':' + name)
    integrity(root, commit, policy_path, policy, approved)
    for iteration in (1, 2):
        for check in policy['checks']:
            print('RUN %s/2 %s [%s]' % (iteration, check['name'], check['kind']), flush=True)
            try:
                result = subprocess.run(check['argv'], cwd=root, timeout=check['timeout'],
                                        shell=False, check=False)
            finally:
                integrity(root, commit, policy_path, policy, approved)
            if result.returncode:
                raise Rejected('Check failed: %s (exit %s)' % (check['name'], result.returncode))
    print('PASS quality: integrity, perimeter and all checks verified twice', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--policy', required=True)
    parser.add_argument('--approved-ref', required=True)
    args = parser.parse_args()
    try:
        approve(Path(args.repo_root), args.policy, args.approved_ref)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('REJECT quality: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
