"""Real public-entry integration checks on disposable template copies."""
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
sys.path.insert(0, str(ROOT / 'scripts'))
import bootstrap_project


DEMO_FILES = (
    'knowledge/tasks/TASK-001.md',
    'knowledge/tasks/TASK-002.md',
    'docs/task-evidence/TASK-001-b9654fbcb1f759c9196edfd64819f8dd1cde435f.json',
    'docs/task-evidence/TASK-002-e42db61052d94c249ae48c08f0f4ea052c2b4e73.json',
)


@unittest.skipUnless((ROOT / 'src/hello.py').is_file(),
                     'template-only integration: project already initialized')
class ProjectInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-new-project-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL=os.devnull)
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR'):
            self.env.pop(name, None)
        files = subprocess.run(
            ['git', '-C', str(ROOT), 'ls-files', '--cached', '--others',
             '--exclude-standard', '-z'], capture_output=True, check=True,
            env=self.env, timeout=30).stdout.decode('utf-8').split('\0')
        for relative in filter(None, files):
            source, target = ROOT / relative, self.root / relative
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        for relative in DEMO_FILES:
            self.assertTrue((self.root / relative).is_file(), relative)

    def run_command(self, *args, expected=0):
        result = subprocess.run(args, cwd=self.root, env=self.env,
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=120)
        self.assertEqual(result.returncode, expected,
                         '{}\n{}{}'.format(args, result.stdout, result.stderr))
        return (result.stdout + result.stderr).strip()

    def python(self, *args, expected=0):
        return self.run_command(sys.executable, *args, expected=expected)

    def git(self, *args):
        return self.run_command('git', *args)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def assert_initialized(self, guide=False):
        for relative in DEMO_FILES:
            self.assertFalse((self.root / relative).exists(), relative)
        self.assertEqual(list((self.root / 'knowledge/tasks').glob('TASK-*.md')), [])
        self.assertEqual(list((self.root / 'docs/task-evidence').glob('*.json')), [])
        policy = json.loads((self.root / 'completion-legacy.json').read_text(encoding='utf-8'))
        self.assertEqual(policy, {'schema_version': 1, 'repository': 'ExampleCo/Shop',
                                  'legacy_pairs': {}})
        self.assertEqual((self.root / 'KDD-START-HERE.md').exists(), guide)
        self.assertTrue((self.root / 'tools/kdd-board/src/git-task-store.ts').is_file())
        self.assertTrue((self.root / 'tests/test_task_git.py').is_file())

    def test_bootstrap_api_applies_real_initializer_with_explicit_repository(self):
        result = bootstrap_project.bootstrap_project(
            str(self.root), True, 'Shop', 'standard', repository='ExampleCo/Shop')
        self.assertTrue(result['applied'])
        self.assertTrue(set(DEMO_FILES).issubset(result['removed']))
        self.assert_initialized(guide=True)
        guide = (self.root / 'KDD-START-HERE.md').read_text(encoding='utf-8')
        self.assertIn('--profile standard --approved-ref <SHA_APROBADO>', guide)
        self.assertIn('Shop', guide)

    def test_bootstrap_cli_applies_real_initializer_and_minimal_guide(self):
        self.python('scripts/bootstrap_project.py', '--apply', '--name', 'Shop',
                    '--profile', 'minimal', '--repository', 'ExampleCo/Shop')
        self.assert_initialized(guide=True)
        guide = (self.root / 'KDD-START-HERE.md').read_text(encoding='utf-8')
        self.assertIn('--profile minimal\n', guide)
        self.assertNotIn('--approved-ref', guide)

    def test_bootstrap_dry_run_without_repository_is_read_only(self):
        before = self.snapshot()
        self.python('scripts/bootstrap_project.py', '--name', 'Shop')
        self.assertEqual(self.snapshot(), before)

    def test_bootstrap_rejects_missing_or_invalid_repository_without_writes(self):
        before = self.snapshot()
        for extra in ([], ['--repository', 'invalid']):
            with self.subTest(extra=extra):
                output = self.python('scripts/bootstrap_project.py', '--apply',
                                     *extra, expected=2)
                self.assertIn('repository', output)
                self.assertEqual(self.snapshot(), before)

    def test_bootstrap_rejects_incomplete_manifest_without_writing_guide(self):
        (self.root / 'src/hello.py').unlink()
        before = self.snapshot()
        output = self.python('scripts/bootstrap_project.py', '--apply',
                             '--repository', 'ExampleCo/Shop', expected=2)
        self.assertIn('manifiesto incompleto', output)
        self.assertEqual(self.snapshot(), before)

    def test_initializer_preserves_project_owned_task_and_evidence_files(self):
        owned = {'knowledge/tasks/TASK-900.md': b'project-owned task\n',
                 'docs/task-evidence/custom-proof.json': b'{"project":"owned"}\n'}
        for relative, content in owned.items():
            (self.root / relative).write_bytes(content)
        self.python('scripts/init_project.py', '--apply', '--repository', 'ExampleCo/Shop')
        for relative in DEMO_FILES:
            self.assertFalse((self.root / relative).exists(), relative)
        for relative, content in owned.items():
            self.assertEqual((self.root / relative).read_bytes(), content)

    def test_new_git_project_validates_and_completes_its_first_task(self):
        self.python('scripts/init_project.py', '--apply', '--repository', 'ExampleCo/Shop')
        self.assert_initialized()
        self.git('init', '-q', '-b', 'main')
        for key, value in (('user.name', 'KDD Integration Test'),
                           ('user.email', 'integration@example.test'),
                           ('core.autocrlf', 'false'), ('commit.gpgsign', 'false')):
            self.git('config', key, value)
        self.git('add', '.')
        self.git('commit', '-qm', 'Initialize independent project')
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')
        self.assertEqual(json.loads(self.python('scripts/tasks.py', 'list', '--json')), [])
        for args in (
            ('scripts/validate_contracts.py', 'knowledge/contracts'),
            ('scripts/validate_okf.py', 'knowledge'),
            ('scripts/validate_specs.py', 'specs'),
            ('scripts/validate_changelog.py',),
            ('scripts/validate_completion.py', '--repository', 'ExampleCo/Shop'),
            ('scripts/validate_tasks.py', '--head-ref', 'main'),
        ):
            with self.subTest(check=args[0]):
                self.python(*args)

        self.write_project_contract()
        self.python('scripts/validate_contracts.py', 'knowledge/contracts')
        self.git('add', '.')
        self.git('commit', '-qm', 'Approve project contract and oracle fixture')
        approved = self.git('rev-parse', 'HEAD')
        self.task('create', '--title', 'Project value', '--description', 'Return seven',
                  '--contract', 'knowledge/contracts/project-value.md')
        self.task('ready', '--approved-ref', approved)
        self.task('start', '--assignee', 'developer')
        self.git('switch', '-q', 'task/TASK-001')
        (self.root / 'src/project_value.py').write_text('def value():\n    return 7\n', encoding='utf-8')
        self.git('add', 'src/project_value.py')
        self.git('commit', '-qm', 'Implement project value')
        self.git('switch', '-q', 'main')
        self.git('merge', '--no-ff', '-qm', 'Integrate task implementation', 'task/TASK-001')
        tested = self.git('rev-parse', 'HEAD')
        result = self.task('finish')
        self.assertEqual(result['task']['status'], 'done')
        self.assertEqual(result['task']['verified_ref'], tested)
        evidence = self.root / result['task']['evidence']
        self.assertEqual(hashlib.sha256(evidence.read_bytes()).hexdigest(),
                         result['task']['evidence_sha256'])
        report = json.loads(evidence.read_text(encoding='utf-8'))
        self.assertEqual(report['exit_code'], 0)
        self.assertEqual(report['passed_tests'], 1)
        self.assertEqual(report['approved_ref'], approved)
        self.assertEqual(report['tested_commit'], tested)
        entries = json.loads(self.python('scripts/tasks.py', 'history', 'TASK-001', '--json'))
        self.assertEqual([entry['status'] for entry in entries],
                         ['backlog', 'ready', 'in_progress', 'done'])
        for entry in entries:
            self.assertEqual(self.git('cat-file', '-t', entry['commit']), 'commit')
        self.python('scripts/validate_tasks.py', '--base-ref', approved, '--head-ref', 'main')
        self.python('scripts/validate_okf.py', 'knowledge')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def task(self, operation, *args):
        return json.loads(self.python('scripts/tasks.py', operation, 'TASK-001', *args, '--json'))

    def write_project_contract(self):
        (self.root / 'src/project_value.py').write_text('def value():\n    return 0\n', encoding='utf-8')
        oracle = ('import unittest\nfrom src.project_value import value\n'
                  'class ProjectValueTests(unittest.TestCase):\n'
                  '    def test_value(self): self.assertEqual(value(), 7)\n')
        (self.root / 'tests/test_project_value.py').write_text(oracle, encoding='utf-8')
        contract = '''---
type: 'Task Contract'
title: 'Project value'
description: 'Return the project value seven'
tags: ['project']
task: project-value
intent: 'Return seven'
target: src/project_value.py
signature: 'def value() -> int:'
test_command: 'python -m unittest tests/test_project_value.py'
budget:
  cyclomatic_max: 2
  nesting_max: 1
tests: tests/test_project_value.py
tests_sha256: 'ORACLE_DIGEST'
touch_only: ['src/project_value.py']
deps_allowed: ['stdlib']
forbids: ['network']
---
## Intent
Return the value of the project.
## Interface
value() -> int.
## Invariants
- Always return seven.
## Examples
- value() -> 7.
- value() == 7.
## Do / Don't
- DO return seven.
- DON'T modify the approved oracle.
## Tests
tests/test_project_value.py.
## Constraints
PARAR y reportar si the oracle changes.
'''
        (self.root / 'knowledge/contracts/project-value.md').write_text(
            contract.replace('ORACLE_DIGEST', hashlib.sha256(oracle.encode('utf-8')).hexdigest()),
            encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
