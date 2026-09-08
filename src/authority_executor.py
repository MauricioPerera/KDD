"""Trusted operation broker. This is not a sandbox for arbitrary code."""
import argparse
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import stat
import threading

from src.authority_policy import COMMANDS, allows_child, matches, parse_policy, valid_path


class _Denied(Exception):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason


@dataclass
class _Scope:
    policy: object
    identifier: str
    used: int = 0


@dataclass
class _State:
    root: Path
    lock: object = field(default_factory=threading.RLock)
    audit: list = field(default_factory=list)
    next_scope: int = 0


def _reparse(info):
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)))


def _request(request):
    if not isinstance(request, dict) or not isinstance(request.get('op'), str):
        raise _Denied('INVALID_REQUEST', None)
    fields = {'read_file': {'op', 'path'}, 'write_file': {'op', 'path', 'text'},
              'run_command': {'op', 'path', 'command'}}
    if request['op'] not in fields:
        raise _Denied('UNSUPPORTED_OPERATION', 'unsupported_operation')
    if set(request) != fields[request['op']]:
        raise _Denied('INVALID_REQUEST', None)
    if not valid_path(request['path']):
        raise _Denied('INVALID_PATH', 'authority_expansion')
    if request['op'] == 'write_file' and not isinstance(request['text'], str):
        raise _Denied('INVALID_REQUEST', None)
    if request['op'] == 'run_command' and request['command'] not in COMMANDS:
        raise _Denied('UNSUPPORTED_COMMAND', 'unsupported_operation')


def _permissions(policy, request):
    path, operation = request['path'], request['op']
    if operation == 'write_file':
        if matches(policy.protected_paths, path):
            raise _Denied('PROTECTED_PATH', 'oracle_change')
        if not matches(policy.write, path) or not matches(policy.touch_only, path):
            raise _Denied('AUTHORITY_DENIED', 'authority_expansion')
    else:
        if not matches(policy.read, path):
            raise _Denied('AUTHORITY_DENIED', 'authority_expansion')
        if operation == 'run_command' and request['command'] not in policy.execute:
            raise _Denied('AUTHORITY_DENIED', 'authority_expansion')


def _safe_path(root, path):
    if root.resolve(strict=True) != root or _reparse(root.lstat()):
        raise _Denied('UNSAFE_PATH', 'authority_expansion')
    current = root
    for segment in path.split('/'):
        current = current / segment
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if _reparse(info):
            raise _Denied('UNSAFE_PATH', 'authority_expansion')
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise _Denied('UNSAFE_PATH', 'authority_expansion')
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            raise _Denied('UNSAFE_PATH', 'authority_expansion')
    if not current.resolve(strict=False).is_relative_to(root):
        raise _Denied('UNSAFE_PATH', 'authority_expansion')
    return current


def _read_bytes(path, limit):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
            raise _Denied('UNSAFE_PATH', 'authority_expansion')
        if info.st_size > limit:
            raise _Denied('SIZE_LIMIT', 'budget_exhausted')
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise _Denied('SIZE_LIMIT', 'budget_exhausted')
    return content


def _invalid_constant(value):
    raise ValueError('Non-JSON numeric constant')


def _run_command(command, content):
    if command == 'sha256':
        return hashlib.sha256(content).hexdigest()
    try:
        json.loads(content.decode('utf-8'), parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        return {'valid': False}
    return {'valid': True}


def _perform(path, request, limit):
    if request['op'] == 'write_file':
        payload = request['text'].encode('utf-8')
        if len(payload) > limit:
            raise _Denied('SIZE_LIMIT', 'budget_exhausted')
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError as exc:
            raise _Denied('OVERWRITE_NOT_SUPPORTED', 'destructive_action') from exc
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
        return {'bytes_written': len(payload)}
    content = _read_bytes(path, limit)
    if request['op'] == 'read_file':
        return content.decode('utf-8')
    return _run_command(request['command'], content)


class AuthorityExecutor:
    def __init__(self, root, policy):
        configured = parse_policy(policy)
        raw = Path(root).absolute()
        try:
            if _reparse(raw.lstat()) or not raw.is_dir():
                raise ValueError('Unsafe workspace root')
            resolved = raw.resolve(strict=True)
        except OSError as exc:
            raise ValueError('Workspace root unavailable') from exc
        self._state = _State(resolved)
        self._chain = (_Scope(configured, 'root'),)

    def delegate(self, child_policy):
        child = parse_policy(child_policy)
        if not allows_child(self._chain[-1].policy, child):
            raise PermissionError('Delegation would expand authority or limits')
        with self._state.lock:
            self._state.next_scope += 1
            handle = object.__new__(AuthorityExecutor)
            handle._state = self._state
            identifier = self._chain[-1].identifier + '/' + str(self._state.next_scope)
            handle._chain = self._chain + (_Scope(child, identifier),)
            return handle

    @property
    def operations_used(self):
        with self._state.lock:
            return self._chain[0].used

    @property
    def audit_log(self):
        with self._state.lock:
            return [dict(event) for event in self._state.audit]

    def _admit(self, request):
        _request(request)
        for scope in self._chain:
            _permissions(scope.policy, request)
        if any(s.used >= s.policy.max_operations for s in self._chain):
            raise _Denied('OPERATION_LIMIT', 'budget_exhausted')
        for scope in self._chain:
            scope.used += 1

    def _record(self, request, result):
        request = request if isinstance(request, dict) else {}
        operation = request.get('op')
        path = request.get('path')
        self._state.audit.append({'sequence': len(self._state.audit) + 1,
                                  'scope': self._chain[-1].identifier,
                                  'operation': operation[:64] if isinstance(operation, str) else None,
                                  'path': path[:512] if isinstance(path, str) else None,
                                  'ok': result['ok'], 'code': result['code']})
        return result

    def execute(self, request: dict) -> dict:
        """Authorize before effects; accepted attempts consume shared quotas."""
        with self._state.lock:
            try:
                self._admit(request)
                path = _safe_path(self._state.root, request['path'])
                limit = min(s.policy.max_bytes for s in self._chain)
                data = _perform(path, request, limit)
                result = {'ok': True, 'code': 'OK', 'data': data}
            except _Denied as denied:
                result = {'ok': False, 'code': denied.code}
                if denied.reason:
                    result['escalation'] = {'required': True, 'reason': denied.reason}
            except (OSError, UnicodeError, ValueError, RuntimeError):
                result = {'ok': False, 'code': 'IO_ERROR'}
            return self._record(request, result)


def _load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _outside_workspace(path, root):
    if path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError('Control policy must live outside the workspace')
    return _load(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--policy', required=True, type=Path)
    parser.add_argument('--requests', required=True, type=Path)
    parser.add_argument('--delegate', action='append', default=[], type=Path)
    args = parser.parse_args()
    try:
        executor = AuthorityExecutor(args.root, _outside_workspace(args.policy, args.root))
        for path in args.delegate:
            executor = executor.delegate(_outside_workspace(path, args.root))
        requests = _load(args.requests)
        if not isinstance(requests, list):
            raise ValueError('Requests must be a list')
        results = [executor.execute(request) for request in requests]
    except (OSError, ValueError, UnicodeError, RecursionError, RuntimeError):
        print(json.dumps({'ok': False, 'code': 'INVALID_CONFIGURATION'}))
        return 2
    print(json.dumps({'results': results, 'operations_used': executor.operations_used,
                      'audit': executor.audit_log}, sort_keys=True))
    return 0 if all(result['ok'] for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
