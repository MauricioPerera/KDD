"""Real Git and process acceptance tests for composed group contracts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'group_contracts.py'


def run(args, cwd):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
               GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid',
               PYTHONUTF8='1')
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                          encoding='utf-8', timeout=30)


class GroupContractsIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'gc.auto', '0')
        self.git('config', 'maintenance.auto', 'false')
        self.write('.gitignore', 'events.log\n__pycache__/\n')
        self.write('src/add.py', 'def add(a, b): return a + b\n')
        self.write('tests/atom.py', "from pathlib import Path\np=Path('events.log')\np.open('a').write('atom\\n')\n")
        self.write('tests/integration.py', "from pathlib import Path\np=Path('events.log')\np.open('a').write('integration\\n')\n")
        self.write('tests/sub.py', "from pathlib import Path\np=Path('events.log')\np.open('a').write('sub\\n')\n")
        self.write('tests/helper.py', 'VALUE = 1\n')
        seal = hashlib.sha256((self.root / 'tests/atom.py').read_bytes()).hexdigest()
        self.write('contracts/atom.md', '''---
type: 'Task Contract'
title: 'Atom'
description: 'A real executable task.'
tags: ['test']
task: atom
intent: 'Run the atomic test.'
target: src/add.py
signature: 'def add(a, b):'
test_command: 'python tests/atom.py'
budget:
  cyclomatic_max: 4
tests: 'tests/atom.py'
tests_sha256: 'SEAL'
touch_only: ['src/add.py']
deps_allowed: []
forbids: ['network']
---
## Intent
Execute a test.
## Interface
add(a, b)
## Invariants
- No network.
## Examples
- One example.
- Another example.
## Do / Don't
- DO run the test.
## Tests
tests/atom.py
## Constraints
PARAR y reportar si no se puede verificar.
'''.replace('SEAL', seal))
        self.group('groups/sub.md', ['contracts/atom.md'], 'tests/sub.py')
        self.group('groups/root.md', ['groups/sub.md', 'contracts/atom.md'], 'tests/integration.py')
        self.approved = self.commit()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')

    def git(self, *args):
        result = run(['git', '-C', str(self.root), *args], self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Review group fixture')
        return self.git('rev-parse', 'HEAD')

    def group(self, path, children, test):
        self.write(path, '\n'.join([
            '---', "type: 'Group Contract'", "title: 'Group'",
            "description: 'A real integration group.'", "tags: ['test']",
            'kind: group', 'children: ' + json.dumps(children),
            'integration_tests: ' + json.dumps([test]),
            'integration_argv: ' + json.dumps(['python', test]),
            "protected: ['tests/helper.py']", '---', '# Group', '']))

    def invoke(self, ref=None, timeout='10'):
        result = run([sys.executable, str(CLI), 'groups/root.md', '--repo-root', str(self.root),
                      '--approved-ref', ref or self.approved, '--timeout', timeout], self.root)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f'CLI must return JSON: {exc}: {result.stdout!r} {result.stderr!r}')
        return result, payload

    def events(self):
        path = self.root / 'events.log'
        return path.read_text(encoding='utf-8').splitlines() if path.exists() else []

    def assert_invalid_before_execution(self):
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 2, payload)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['verdict'], 'INVALID')
        self.assertEqual(self.events(), [])

    def test_nested_group_executes_shared_child_once_and_in_order(self):
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 0, payload)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['verdict'], 'PASS')
        self.assertEqual(payload['approved_ref'], self.approved)
        self.assertEqual(payload['executed'], ['contracts/atom.md', 'groups/sub.md', 'groups/root.md'])
        self.assertEqual(self.events(), ['atom', 'sub', 'integration'])

    def test_atomic_failure_prevents_parent_integration(self):
        self.write('tests/atom.py', "raise SystemExit(7)\n")
        seal = hashlib.sha256((self.root / 'tests/atom.py').read_bytes()).hexdigest()
        contract = self.root / 'contracts/atom.md'
        import re
        contract.write_text(re.sub(r"tests_sha256: '[0-9a-f]+'", "tests_sha256: '" + seal + "'",
                                   contract.read_text(encoding='utf-8')), encoding='utf-8')
        self.approved = self.commit()
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 1, payload)
        self.assertFalse(payload['ok'])
        self.assertEqual((payload['verdict'], payload['stage']), ('FAIL', 'atomic'))
        self.assertEqual(self.events(), [])

    def test_integration_failure_is_not_pass(self):
        self.write('tests/integration.py', 'raise SystemExit(9)\n')
        self.approved = self.commit()
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 1, payload)
        self.assertFalse(payload['ok'])
        self.assertEqual((payload['verdict'], payload['stage']), ('FAIL', 'integration'))
        self.assertEqual(self.events(), ['atom', 'sub'])

    def test_changed_atomic_oracle_is_rejected_before_any_execution(self):
        self.write('tests/atom.py', 'print(123)\n')
        self.assert_invalid_before_execution()

    def test_changed_integration_oracle_is_rejected_before_any_execution(self):
        self.write('tests/integration.py', 'print(123)\n')
        self.assert_invalid_before_execution()

    def test_changed_protected_helper_is_rejected_before_any_execution(self):
        self.write('tests/helper.py', 'VALUE = 2\n')
        self.assert_invalid_before_execution()

    def test_symlink_blob_in_approved_index_is_rejected(self):
        blob = self.git('hash-object', '-w', 'tests/helper.py')
        self.git('update-index', '--cacheinfo', '120000,' + blob + ',tests/helper.py')
        self.git('commit', '-qm', 'Approved symlink fixture')
        self.approved = self.git('rev-parse', 'HEAD')
        self.assert_invalid_before_execution()

    def test_changed_group_is_rejected_before_any_execution(self):
        self.group('groups/root.md', ['contracts/atom.md'], 'tests/integration.py')
        self.assert_invalid_before_execution()

    def test_changed_atomic_contract_is_rejected_before_any_execution(self):
        p = self.root / 'contracts/atom.md'
        p.write_text(p.read_text(encoding='utf-8').replace('tests/atom.py', 'tests/sub.py'),
                     encoding='utf-8')
        self.assert_invalid_before_execution()

    def test_staged_protected_change_is_rejected_even_if_worktree_restored(self):
        self.write('tests/helper.py', 'VALUE = 2\n')
        self.git('add', 'tests/helper.py')
        self.write('tests/helper.py', 'VALUE = 1\n')
        self.assert_invalid_before_execution()

    def test_worktree_crlf_matches_approved_lf_for_utf8_files(self):
        (self.root / 'tests/helper.py').write_bytes(b'VALUE = 1\r\n')
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 0, payload)
        self.assertTrue(payload['ok'])
        self.assertEqual(self.events(), ['atom', 'sub', 'integration'])

    def test_cycle_is_rejected_before_any_execution(self):
        self.group('groups/sub.md', ['groups/root.md'], 'tests/sub.py')
        self.approved = self.commit()
        self.assert_invalid_before_execution()

    def test_missing_child_is_rejected_before_any_execution(self):
        self.group('groups/root.md', ['contracts/atom.md', 'contracts/missing.md'], 'tests/integration.py')
        self.approved = self.commit()
        self.assert_invalid_before_execution()

    def test_duplicate_children_in_one_group_are_rejected(self):
        self.group('groups/root.md', ['contracts/atom.md', 'contracts/atom.md'], 'tests/integration.py')
        self.approved = self.commit()
        self.assert_invalid_before_execution()

    def test_outside_child_is_rejected_before_any_execution(self):
        self.group('groups/root.md', ['../outside.md'], 'tests/integration.py')
        self.approved = self.commit()
        self.assert_invalid_before_execution()

    def test_moving_reference_is_not_an_approved_commit(self):
        result, payload = self.invoke(ref='HEAD')
        self.assertEqual(result.returncode, 2, payload)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['verdict'], 'INVALID')
        self.assertEqual(self.events(), [])

    def test_integration_oracle_must_be_named_in_argv(self):
        self.group('groups/root.md', ['contracts/atom.md'], 'tests/integration.py')
        p = self.root / 'groups/root.md'
        p.write_text(p.read_text(encoding='utf-8').replace(
            '"tests/integration.py"]\nprotected', '"tests/sub.py"]\nprotected'), encoding='utf-8')
        self.approved = self.commit()
        self.assert_invalid_before_execution()

    def test_mutation_during_command_invalidates_group(self):
        self.write('tests/atom.py', "from pathlib import Path\nPath('tests/helper.py').write_text('MUTATED')\n")
        seal = hashlib.sha256((self.root / 'tests/atom.py').read_bytes()).hexdigest()
        contract = self.root / 'contracts/atom.md'
        import re
        contract.write_text(re.sub(r"tests_sha256: '[0-9a-f]+'", "tests_sha256: '" + seal + "'",
                                   contract.read_text(encoding='utf-8')), encoding='utf-8')
        self.approved = self.commit()
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 2, payload)
        self.assertFalse(payload['ok'])
        self.assertEqual((payload['verdict'], payload['stage']), ('INVALID', 'inputs-changed'))
        self.assertEqual(self.events(), [])

    def test_index_mutation_during_command_invalidates_group(self):
        self.write('tests/atom.py', "from pathlib import Path\nimport subprocess\n"
                   "p=Path('tests/helper.py')\nold=p.read_bytes()\np.write_text('MUTATED')\n"
                   "subprocess.run(['git','add','tests/helper.py'],check=True)\np.write_bytes(old)\n")
        seal = hashlib.sha256((self.root / 'tests/atom.py').read_bytes()).hexdigest()
        contract = self.root / 'contracts/atom.md'
        import re
        contract.write_text(re.sub(r"tests_sha256: '[0-9a-f]+'", "tests_sha256: '" + seal + "'",
                                   contract.read_text(encoding='utf-8')), encoding='utf-8')
        self.approved = self.commit()
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 2, payload)
        self.assertEqual((payload['verdict'], payload['stage']), ('INVALID', 'inputs-changed'))
        self.assertEqual(self.events(), [])

    def test_nonpositive_timeout_is_rejected_before_any_execution(self):
        result, payload = self.invoke(timeout='0')
        self.assertEqual(result.returncode, 2, payload)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['verdict'], 'INVALID')
        self.assertEqual(self.events(), [])

    def test_real_integration_process_timeout_is_not_pass(self):
        self.write('tests/integration.py', 'import time\ntime.sleep(20)\n')
        self.approved = self.commit()
        result, payload = self.invoke(timeout='2')
        self.assertEqual(result.returncode, 2, payload)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['verdict'], 'TIMEOUT')
        self.assertEqual(self.events(), ['atom', 'sub'])

    def test_integration_argv_is_not_interpreted_by_shell(self):
        self.write('tests/integration.py', "import sys\nassert sys.argv[1] == ';echo unsafe'\n")
        path = self.root / 'groups/root.md'
        text = path.read_text(encoding='utf-8').replace(
            '"tests/integration.py"]\nprotected',
            '"tests/integration.py", ";echo unsafe"]\nprotected')
        path.write_text(text, encoding='utf-8')
        self.approved = self.commit()
        result, payload = self.invoke()
        self.assertEqual(result.returncode, 0, payload)
        self.assertTrue(payload['ok'])
        self.assertEqual(self.events(), ['atom', 'sub'])

    def test_group_node_passes_real_okf_validation(self):
        self.group('knowledge/groups/example.md', ['contracts/atom.md'], 'tests/integration.py')
        self.write('knowledge/index.md', '# Index\n\n- [Group](./groups/example.md)\n')
        result = run([sys.executable, str(ROOT / 'scripts/validate_okf.py'),
                      str(self.root / 'knowledge')], self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_sha256_repository_uses_full_native_commit_id(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name in ('src', 'tests', 'contracts', 'groups'):
            shutil.copytree(self.root / name, root / name)
        (root / '.gitignore').write_text('events.log\n__pycache__/\n', encoding='utf-8')
        for command in (['init', '-q', '--object-format=sha256'],
                        ['config', 'core.autocrlf', 'false'], ['config', 'gc.auto', '0'],
                        ['config', 'maintenance.auto', 'false'], ['add', '.'],
                        ['commit', '-qm', 'SHA256 reviewed fixture']):
            result = run(['git', '-C', str(root), *command], root)
            self.assertEqual(result.returncode, 0, result.stderr)
        ref = run(['git', '-C', str(root), 'rev-parse', 'HEAD'], root).stdout.strip()
        self.assertEqual(len(ref), 64)
        result = run([sys.executable, str(CLI), 'groups/root.md', '--repo-root', str(root),
                      '--approved-ref', ref, '--timeout', '10'], root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['approved_ref'], ref)


if __name__ == '__main__':
    unittest.main()
