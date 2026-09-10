"""Reproducible authority demo; all effects stay in a temporary directory."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from src.authority_executor import AuthorityExecutor


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    policy = {
        'version': 1,
        'authority': {'read': ['allowed/**', 'tests/**'],
                      'write': ['allowed/**', 'tests/**'], 'execute': ['sha256']},
        'touch_only': ['allowed/**', 'tests/**'], 'protected_paths': ['tests/**'],
        'limits': {'max_operations': 4, 'max_bytes': 1024},
    }
    with tempfile.TemporaryDirectory(prefix='kdd-authority-') as directory:
        root = Path(directory)
        for name in ('allowed', 'tests'):
            (root / name).mkdir()
        (root / 'tests/oracle.txt').write_text('frozen oracle', encoding='utf-8')
        executor = AuthorityExecutor(root, policy)
        allowed = executor.execute({'op': 'write_file', 'path': 'allowed/result.txt',
                                    'text': 'authorized'})
        if not allowed['ok'] or (root / 'allowed/result.txt').read_text() != 'authorized':
            raise AssertionError(allowed)
        child_policy = copy.deepcopy(policy)
        child_policy['authority']['write'] = ['allowed/child.txt']
        child_policy['touch_only'] = ['allowed/child.txt']
        child = executor.delegate(child_policy)
        before = snapshot(root)
        denied = [
            executor.execute({'op': 'write_file', 'path': 'tests/oracle.txt', 'text': 'changed'}),
            executor.execute({'op': 'run_command', 'path': 'allowed/result.txt', 'command': 'shell'}),
            child.execute({'op': 'write_file', 'path': 'allowed/parent.txt', 'text': 'expanded'}),
        ]
        unchanged = before == snapshot(root)
        if not unchanged or any(result['ok'] for result in denied):
            raise AssertionError(denied)
        print(json.dumps({'allowed': allowed['ok'], 'denied': [r['code'] for r in denied],
                          'denied_effects_absent': unchanged,
                          'operations_used': executor.operations_used,
                          'audit': executor.audit_log}, indent=2))


if __name__ == '__main__':
    main()
