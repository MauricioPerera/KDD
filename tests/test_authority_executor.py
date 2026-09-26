"""Acceptance oracle: permission denial must precede filesystem effects."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from src.authority_executor import AuthorityExecutor


def policy():
    return {'version': 1,
            'authority': {'read': ['allowed/**', 'tests/**'],
                          'write': ['allowed/**', 'tests/**'],
                          'execute': ['sha256', 'validate_json']},
            'touch_only': ['allowed/**', 'tests/**'],
            'protected_paths': ['tests/**'],
            'limits': {'max_operations': 10, 'max_bytes': 4096}}


def manifest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'workspace'
        for name in ['allowed', 'private', 'tests']:
            (self.root / name).mkdir(parents=True)
        (self.root / 'allowed/data.json').write_text('{"value": 7}', encoding='utf-8')
        (self.root / 'private/secret.txt').write_text('do-not-disclose', encoding='utf-8')
        (self.root / 'tests/oracle.py').write_text('assert 1 == 1', encoding='utf-8')
        self.executor = AuthorityExecutor(self.root, policy())

    def test_create_then_read(self):
        result = self.executor.execute({'op': 'write_file', 'path': 'allowed/new.txt', 'text': 'hello'})
        self.assertTrue(result['ok'], result)
        self.assertEqual((self.root / 'allowed/new.txt').read_text(), 'hello')
        result = self.executor.execute({'op': 'read_file', 'path': 'allowed/new.txt'})
        self.assertEqual(result['data'], 'hello')

    def test_commands_are_internal_and_read_only(self):
        before = manifest(self.root)
        result = self.executor.execute({'op': 'run_command', 'path': 'allowed/data.json', 'command': 'sha256'})
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['data'], hashlib.sha256((self.root / 'allowed/data.json').read_bytes()).hexdigest())
        result = self.executor.execute({'op': 'run_command', 'path': 'allowed/data.json', 'command': 'validate_json'})
        self.assertEqual(result['data'], {'valid': True})
        self.assertEqual(manifest(self.root), before)

    def test_invalid_json_is_not_executed(self):
        (self.root / 'allowed/code.txt').write_text('NaN', encoding='utf-8')
        result = self.executor.execute({'op': 'run_command', 'path': 'allowed/code.txt', 'command': 'validate_json'})
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['data'], {'valid': False})

    def test_static_denials_have_no_effects(self):
        before = manifest(self.root)
        attempts = [
            {'op': 'write_file', 'path': 'private/new.txt', 'text': 'bad'},
            {'op': 'write_file', 'path': 'tests/oracle.py', 'text': 'assert True'},
            {'op': 'read_file', 'path': 'private/secret.txt'},
            {'op': 'run_command', 'path': 'allowed/data.json', 'command': 'shell'},
            {'op': 'run_command', 'path': 'private/secret.txt', 'command': 'sha256'},
        ]
        for request in attempts:
            with self.subTest(request=request):
                result = self.executor.execute(request)
                self.assertFalse(result['ok'])
                self.assertTrue(result['escalation']['required'])
                self.assertNotIn('do-not-disclose', json.dumps(result))
                self.assertEqual(manifest(self.root), before)
        self.assertEqual(self.executor.operations_used, 0)

    def test_execute_permission_not_implied_by_read(self):
        configured = policy()
        configured['authority']['execute'] = []
        result = AuthorityExecutor(self.root, configured).execute(
            {'op': 'run_command', 'path': 'allowed/data.json', 'command': 'sha256'})
        self.assertFalse(result['ok'])

    def test_touch_only_intersection(self):
        configured = policy()
        configured['touch_only'] = ['allowed/single.txt']
        executor = AuthorityExecutor(self.root, configured)
        self.assertFalse(executor.execute({'op': 'write_file', 'path': 'allowed/other.txt', 'text': 'bad'})['ok'])
        self.assertTrue(executor.execute({'op': 'write_file', 'path': 'allowed/single.txt', 'text': 'ok'})['ok'])

    def test_existing_file_never_overwritten(self):
        before = manifest(self.root)
        result = self.executor.execute({'op': 'write_file', 'path': 'allowed/data.json', 'text': 'bad'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['code'], 'OVERWRITE_NOT_SUPPORTED')
        self.assertTrue(result['escalation']['required'])
        self.assertEqual(manifest(self.root), before)

    def test_path_escape_and_windows_aliases(self):
        before = manifest(self.root)
        paths = ['../outside.txt', '/outside.txt', 'C:/outside.txt', 'allowed/../private/x',
                 'allowed\\x', 'allowed//x', 'allowed/./x', 'allowed/x:stream',
                 'allowed/NUL', 'allowed/CON.txt', 'allowed/x.', 'allowed/x ', 'allowed/a\x00b']
        for path in paths:
            with self.subTest(path=path):
                result = self.executor.execute({'op': 'write_file', 'path': path, 'text': 'bad'})
                self.assertFalse(result['ok'])
        self.assertEqual(manifest(self.root), before)
        self.assertFalse((self.base / 'outside.txt').exists())

    def test_request_cannot_supply_authority_or_command_args(self):
        before = manifest(self.root)
        for data in [None, [], {}, {'op': 'shell', 'path': 'allowed/x'},
                     {'op': 'write_file', 'path': 'allowed/x', 'text': 'bad', 'approved': True},
                     {'op': 'read_file', 'path': 'allowed/data.json', 'authority': {'read': ['**']}},
                     {'op': 'run_command', 'path': 'allowed/data.json', 'command': 'sha256', 'args': ['--help']}]:
            self.assertFalse(self.executor.execute(data)['ok'])
        self.assertEqual(manifest(self.root), before)

    def test_policy_fail_closed(self):
        cases = [None, {}, {'version': 1}]
        for key, value in [('version', True), ('version', 2), ('external', {'network': False})]:
            p = policy()
            p[key] = value
            cases.append(p)
        for value in [0, True, None, 1.5]:
            p = policy()
            p['limits']['max_operations'] = value
            cases.append(p)
        for value in ['allowed/*', '../**', '/**', 'allowed\\**']:
            p = policy()
            p['authority']['read'] = [value]
            cases.append(p)
        p = policy()
        p['authority']['execute'] = ['shell']
        cases.append(p)
        for configured in cases:
            with self.subTest(configured=configured):
                with self.assertRaises(ValueError):
                    AuthorityExecutor(self.root, configured)

    def test_policy_input_is_not_live(self):
        configured = policy()
        executor = AuthorityExecutor(self.root, configured)
        configured['authority']['write'].append('private/**')
        configured['touch_only'].append('private/**')
        self.assertFalse(executor.execute({'op': 'write_file', 'path': 'private/x', 'text': 'bad'})['ok'])

    def test_child_cannot_expand_authority(self):
        before = manifest(self.root)
        for key in ['read', 'write']:
            child = policy()
            child['authority'][key] = ['**']
            with self.assertRaises(PermissionError):
                self.executor.delegate(child)
        child = policy()
        child['touch_only'] = ['**']
        with self.assertRaises(PermissionError):
            self.executor.delegate(child)
        child = policy()
        child['limits']['max_operations'] = 100
        with self.assertRaises(PermissionError):
            self.executor.delegate(child)
        self.assertEqual(manifest(self.root), before)

    def test_child_denial_and_ancestor_protection(self):
        child_policy = policy()
        child_policy['authority']['write'] = ['allowed/child.txt', 'tests/**']
        child_policy['protected_paths'] = []
        child = self.executor.delegate(child_policy)
        before = manifest(self.root)
        self.assertFalse(child.execute({'op': 'write_file', 'path': 'allowed/parent.txt', 'text': 'bad'})['ok'])
        self.assertFalse(child.execute({'op': 'write_file', 'path': 'tests/oracle.py', 'text': 'bad'})['ok'])
        self.assertEqual(manifest(self.root), before)
        self.assertTrue(child.execute({'op': 'write_file', 'path': 'allowed/child.txt', 'text': 'ok'})['ok'])
        grandchild_policy = copy.deepcopy(child_policy)
        grandchild_policy['authority']['write'] = ['allowed/**']
        with self.assertRaises(PermissionError):
            child.delegate(grandchild_policy)

    def test_shared_budget_and_child_quota(self):
        configured = policy()
        configured['limits']['max_operations'] = 2
        root = AuthorityExecutor(self.root, configured)
        child_policy = copy.deepcopy(configured)
        child_policy['limits']['max_operations'] = 1
        child = root.delegate(child_policy)
        request = {'op': 'read_file', 'path': 'allowed/data.json'}
        self.assertTrue(child.execute(request)['ok'])
        self.assertFalse(child.execute(request)['ok'])
        self.assertTrue(root.delegate(child_policy).execute(request)['ok'])
        self.assertFalse(root.execute(request)['ok'])
        self.assertEqual(root.operations_used, 2)

    def test_concurrent_shared_budget(self):
        configured = policy()
        configured['limits']['max_operations'] = 3
        root = AuthorityExecutor(self.root, configured)
        children = [root.delegate(configured) for _ in range(12)]
        def run(pair):
            index, child = pair
            return child.execute({'op': 'write_file', 'path': f'allowed/{index}.txt', 'text': 'ok'})
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(run, enumerate(children)))
        self.assertEqual(sum(r['ok'] for r in results), 3)
        self.assertEqual(len(list((self.root / 'allowed').glob('*.txt'))), 3)
        self.assertEqual(root.operations_used, 3)

    def test_size_limits_and_missing_parent_have_no_effects(self):
        configured = policy()
        configured['limits']['max_bytes'] = 4
        executor = AuthorityExecutor(self.root, configured)
        before = manifest(self.root)
        self.assertFalse(executor.execute({'op': 'write_file', 'path': 'allowed/large', 'text': '12345'})['ok'])
        self.assertFalse(executor.execute({'op': 'read_file', 'path': 'allowed/data.json'})['ok'])
        self.assertFalse(executor.execute({'op': 'write_file', 'path': 'allowed/missing/file', 'text': 'ok'})['ok'])
        self.assertFalse((self.root / 'allowed/missing').exists())
        self.assertEqual(manifest(self.root), before)

    def test_symlinks_rejected(self):
        link = self.root / 'allowed/link'
        try:
            link.symlink_to(self.root / 'private', target_is_directory=True)
        except OSError:
            self.skipTest('Creating symlinks requires OS privileges')
        self.assertFalse(self.executor.execute({'op': 'write_file', 'path': 'allowed/link/new', 'text': 'bad'})['ok'])
        self.assertFalse(self.executor.execute({'op': 'read_file', 'path': 'allowed/link/secret.txt'})['ok'])
        self.assertFalse((self.root / 'private/new').exists())

    def test_hardlinks_rejected(self):
        link = self.root / 'allowed/alias'
        try:
            os.link(self.root / 'private/secret.txt', link)
        except OSError:
            self.skipTest('Filesystem does not support hardlinks')
        self.assertFalse(self.executor.execute({'op': 'read_file', 'path': 'allowed/alias'})['ok'])

    def test_audit_has_no_payload_and_is_copy(self):
        self.executor.execute({'op': 'read_file', 'path': 'allowed/data.json'})
        self.executor.execute({'op': 'write_file', 'path': 'private/x', 'text': 'sensitive-payload'})
        audit = self.executor.audit_log
        self.assertEqual([event['sequence'] for event in audit], [1, 2])
        self.assertNotIn('sensitive-payload', json.dumps(audit))
        self.assertNotIn('"value"', json.dumps(audit))
        audit.clear()
        self.assertEqual(len(self.executor.audit_log), 2)

    def test_cli_delegation(self):
        policy_file = self.base / 'policy.json'
        child_file = self.base / 'child.json'
        requests = self.base / 'requests.json'
        policy_file.write_text(json.dumps(policy()), encoding='utf-8')
        child_policy = policy()
        child_policy['authority']['write'] = ['allowed/child.txt']
        child_file.write_text(json.dumps(child_policy), encoding='utf-8')
        requests.write_text(json.dumps([
            {'op': 'write_file', 'path': 'allowed/child.txt', 'text': 'ok'},
            {'op': 'write_file', 'path': 'allowed/parent.txt', 'text': 'bad'}]), encoding='utf-8')
        process = subprocess.run([sys.executable, '-m', 'src.authority_executor',
                                  '--root', str(self.root), '--policy', str(policy_file),
                                  '--delegate', str(child_file), '--requests', str(requests)],
                                 cwd=Path(__file__).resolve().parents[1],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 1, process.stderr)
        result = json.loads(process.stdout)
        self.assertTrue(result['results'][0]['ok'])
        self.assertFalse(result['results'][1]['ok'])
        self.assertEqual((self.root / 'allowed/child.txt').read_text(), 'ok')
        self.assertFalse((self.root / 'allowed/parent.txt').exists())


if __name__ == '__main__':
    unittest.main()
