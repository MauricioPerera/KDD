"""Frozen integration oracle for commits, branches and actual test evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import task_git as journal
import task_model as model


class Repository:
    def __init__(self, oracle=None, *, automatic_maintenance=False):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ['scripts', 'knowledge/contracts', 'src', 'tests']:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        for name in ['task_model.py', 'task_git.py', 'task_evidence.py', 'tasks.py',
                     'validate_tasks.py', 'validate_contracts.py', 'validate_baseline.py',
                     'validate_test_commands.py']:
            shutil.copyfile(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        (self.root / '.gitignore').write_text('__pycache__/\n*.pyc\n')
        (self.root / 'knowledge/index.md').write_text('[Contracts](contracts/)\n')
        (self.root / 'src/value.py').write_text('def value():\n    return 7\n')
        (self.root / 'src/__init__.py').write_text('')
        self.oracle = oracle or ('import unittest\nfrom src.value import value\n'
                                  'class ValueTests(unittest.TestCase):\n'
                                  ' def test_value(self): self.assertEqual(value(), 7)\n')
        (self.root / 'tests/test_value.py').write_text(self.oracle, encoding='utf-8')
        digest = hashlib.sha256(self.oracle.encode()).hexdigest()
        self.contract = 'knowledge/contracts/value.md'
        (self.root / self.contract).write_text('''---
type: 'Task Contract'
title: 'Value'
description: 'Validate value'
tags: ['test']
task: value
intent: 'Validate value'
target: src/value.py
signature: 'def value() -> int:'
test_command: 'python -m unittest tests/test_value.py'
budget:
  cyclomatic_max: 4
  nesting_max: 2
tests: tests/test_value.py
tests_sha256: 'DIGEST'
touch_only: ['src/value.py']
deps_allowed: ['stdlib']
forbids: ['network']
---
## Intent
Validate a value.
## Interface
value() -> int.
## Invariants
- Returns seven.
## Examples
- value() -> 7.
- value() == 7.
## Do / Don't
- DO use the approved oracle.
## Tests
tests/test_value.py.
## Constraints
PARAR y reportar si the oracle changes.
'''.replace('DIGEST', digest), encoding='utf-8')
        self.git('init', '-q', '-b', 'main')
        configure_git(self.root, {'maintenance.autoDetach': 'false', 'gc.autoDetach': 'false',
            'user.name': 'KDD Task Test', 'user.email': 'tasks@example.test', 'core.autocrlf': 'false'},
            ephemeral=not automatic_maintenance)
        self.approved = self.commit('approved contract')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
                                       stderr=subprocess.PIPE, text=True).strip()

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def act(self, action, task_id='TASK-001', **options):
        defaults = {'title': 'Validate value', 'description': 'Validate value input',
                    'contract': self.contract, 'depends_on': []}
        return journal.mutate(self.root, action, task_id, defaults | options)

    def start(self):
        self.act('create')
        self.act('ready', approved_ref=self.approved)
        return self.act('start', assignee='developer')

    def integrate(self):
        self.git('switch', '-q', 'task/TASK-001')
        (self.root / 'src/value.py').write_text('def value():\n    return 7  # implemented\n')
        tip = self.commit('implement TASK-001')
        self.git('switch', '-q', 'main')
        self.git('merge', '--no-ff', '-qm', 'integrate TASK-001', 'task/TASK-001')
        return tip

    def close(self):
        self.temp.cleanup()


class TaskJournalTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.addCleanup(self.repo.close)

    def test_each_state_change_is_a_scoped_commit_on_main(self):
        created = self.repo.act('create')
        path = 'knowledge/tasks/TASK-001.md'
        self.assertEqual(self.repo.git('rev-parse', 'HEAD'), created['commit'])
        self.assertEqual(set(self.repo.git('diff-tree', '--no-commit-id', '--name-only', '-r',
                                         created['commit']).splitlines()),
                         {path, 'knowledge/index.md'})
        self.repo.act('ready', approved_ref=self.repo.approved)
        parent = self.repo.git('rev-parse', 'HEAD')
        started = self.repo.act('start', assignee='developer')
        self.assertEqual(self.repo.git('rev-parse', 'task/TASK-001'), parent)
        self.assertEqual(started['task']['status'], 'in_progress')
        self.assertEqual(self.repo.git('branch', '--show-current'), 'main')
        self.assertEqual(self.repo.git('status', '--porcelain'), '')

    def test_dirty_index_and_untracked_files_are_preserved(self):
        for staged in [False, True]:
            with self.subTest(staged=staged):
                (self.repo.root / 'unrelated.txt').write_text('keep')
                if staged:
                    self.repo.git('add', 'unrelated.txt')
                before = self.repo.git('status', '--porcelain')
                with self.assertRaises(model.TaskError):
                    self.repo.act('create')
                self.assertEqual(self.repo.git('status', '--porcelain'), before)
                self.assertEqual((self.repo.root / 'unrelated.txt').read_text(), 'keep')
                self.repo.git('reset', '-q')

    def test_mutations_refuse_task_branch_and_branch_collision(self):
        self.repo.act('create')
        self.repo.act('ready', approved_ref=self.repo.approved)
        self.repo.git('branch', 'task/TASK-001')
        with self.assertRaises(model.TaskError):
            self.repo.act('start', assignee='developer')
        self.repo.git('switch', '-q', 'task/TASK-001')
        with self.assertRaises(model.TaskError):
            self.repo.act('block', reason='decision required')

    def test_failed_commit_rolls_back_created_files(self):
        head = self.repo.git('rev-parse', 'HEAD')
        original = journal.git
        def fail_commit(root, *args):
            if args and args[0] == 'commit':
                raise model.TaskError('simulated commit failure')
            return original(root, *args)
        with patch.object(journal, 'git', side_effect=fail_commit):
            with self.assertRaises(model.TaskError):
                self.repo.act('create')
        self.assertEqual(self.repo.git('rev-parse', 'HEAD'), head)
        self.assertFalse((self.repo.root / 'knowledge/tasks/TASK-001.md').exists())
        self.assertEqual(self.repo.git('status', '--porcelain'), '')

    def test_approval_is_explicit_and_contract_cannot_be_resealed(self):
        self.repo.act('create')
        with self.assertRaises(model.TaskError):
            self.repo.act('ready')
        path = self.repo.root / self.repo.contract
        path.write_text(path.read_text().replace('Validate a value.', 'Changed scope.'), encoding='utf-8')
        self.repo.commit('change contract')
        with self.assertRaises(model.TaskError):
            self.repo.act('ready', approved_ref=self.repo.approved)

    def test_block_resume_reuses_branch_without_resetting_work(self):
        self.repo.start()
        tip = self.repo.integrate()
        self.repo.act('block', reason='Need a decision')
        self.repo.act('resume', reason='Decision recorded')
        self.repo.act('start', assignee='developer')
        self.assertEqual(self.repo.git('rev-parse', 'task/TASK-001'), tip)

    def test_finish_requires_integration_and_records_real_evidence(self):
        self.repo.start()
        with self.assertRaises(model.TaskError):
            self.repo.act('finish')
        tip = self.repo.integrate()
        tested = self.repo.git('rev-parse', 'HEAD')
        result = self.repo.act('finish')
        task = result['task']
        self.assertEqual(task['status'], 'done')
        self.assertEqual(task['verified_ref'], tested)
        self.assertEqual(self.repo.git('rev-parse', 'HEAD^'), tested)
        evidence = (self.repo.root / task['evidence']).read_bytes()
        report = json.loads(evidence)
        self.assertEqual(hashlib.sha256(evidence).hexdigest(), task['evidence_sha256'])
        self.assertEqual(report['tested_commit'], tested)
        self.assertEqual(report['branch_tip'], tip)
        self.assertEqual(report['exit_code'], 0)
        self.assertEqual(report['passed_tests'], 1)
        self.assertEqual(self.repo.git('status', '--porcelain'), '')

    def test_zero_tests_and_failed_tests_never_finish(self):
        for oracle in ['# no tests\n',
                       'import unittest\nclass Bad(unittest.TestCase):\n def test_bad(self): self.fail()\n']:
            with self.subTest(oracle=oracle):
                repo = Repository(oracle)
                try:
                    repo.start()
                    repo.integrate()
                    head = repo.git('rev-parse', 'HEAD')
                    with self.assertRaises(model.TaskError):
                        repo.act('finish')
                    self.assertEqual(repo.git('rev-parse', 'HEAD'), head)
                    self.assertEqual(repo.git('status', '--porcelain'), '')
                finally:
                    repo.close()

    def test_dependencies_and_missing_owners_block_start(self):
        self.repo.act('create', 'TASK-002')
        self.repo.act('create', depends_on=['TASK-002'])
        self.repo.act('ready', approved_ref=self.repo.approved)
        with self.assertRaises(model.TaskError):
            self.repo.act('start', assignee='developer')
        with self.assertRaises(model.TaskError):
            self.repo.act('start')

    def test_readers_use_main_from_a_task_checkout(self):
        self.repo.start()
        self.repo.git('switch', '-q', 'task/TASK-001')
        self.assertEqual(journal.read_tasks(self.repo.root)['TASK-001']['status'], 'in_progress')
        entries = journal.history(self.repo.root, 'TASK-001')
        self.assertEqual([e['status'] for e in entries], ['backlog', 'ready', 'in_progress'])


if __name__ == '__main__':
    unittest.main()
