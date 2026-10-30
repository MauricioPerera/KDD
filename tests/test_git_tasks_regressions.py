"""Independent adversarial checks beyond the initial sealed task oracles."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import tests.test_task_git as fixtures
import task_evidence as proof
import task_git as journal
import task_model as model
import validate_tasks as gate


class GitTaskRegressions(unittest.TestCase):
    def setUp(self):
        self.repo = fixtures.Repository()
        self.addCleanup(self.repo.close)

    def test_commit_failure_drops_only_the_new_branch(self):
        self.repo.act('create')
        self.repo.act('ready', approved_ref=self.repo.approved)
        head = self.repo.git('rev-parse', 'HEAD')
        original = journal.git
        def fail_commit(root, *args):
            if args and args[0] == 'commit':
                raise model.TaskError('commit refused')
            return original(root, *args)
        with patch.object(journal, 'git', side_effect=fail_commit):
            with self.assertRaises(model.TaskError):
                self.repo.act('start', assignee='owner')
        self.assertEqual(self.repo.git('rev-parse', 'HEAD'), head)
        self.assertNotIn('task/TASK-001', self.repo.git('branch', '--list'))
        self.assertEqual(self.repo.git('status', '--porcelain'), '')

    def test_existing_coordinator_lock_is_preserved(self):
        lock = self.repo.root / '.git/kdd-tasks.lock'
        lock.write_text('another coordinator')
        with self.assertRaises(model.TaskError):
            self.repo.act('create')
        self.assertEqual(lock.read_text(), 'another coordinator')

    def test_timeout_cannot_publish_a_close(self):
        self.repo.start()
        self.repo.integrate()
        head = self.repo.git('rev-parse', 'HEAD')
        with patch.object(proof.subprocess, 'run', side_effect=subprocess.TimeoutExpired('oracle', 1)):
            with self.assertRaises(model.TaskError):
                proof.execute({'test_command': 'python -m unittest tests/test_value.py',
                               'tests': 'tests/test_value.py'}, self.repo.root, 1)
        self.assertEqual(self.repo.git('rev-parse', 'HEAD'), head)
        self.assertEqual(journal.read_tasks(self.repo.root)['TASK-001']['status'], 'in_progress')

    def test_oracle_editing_product_files_is_detected_and_preserved(self):
        oracle = ('import unittest\nfrom pathlib import Path\n'
                  'class Tests(unittest.TestCase):\n'
                  " def test_change(self):\n  Path('src/value.py').write_text('modified by test')\n  self.assertTrue(True)\n")
        repo = fixtures.Repository(oracle)
        try:
            repo.start()
            repo.integrate()
            head = repo.git('rev-parse', 'HEAD')
            with self.assertRaises(model.TaskError):
                repo.act('finish')
            self.assertEqual(repo.git('rev-parse', 'HEAD'), head)
            self.assertEqual((repo.root / 'src/value.py').read_text(), 'modified by test')
        finally:
            repo.close()

    def test_valid_node_oracle_can_complete_and_be_audited(self):
        script = "import {test} from 'node:test'; import assert from 'node:assert/strict'; test('value',()=>assert.equal(7,7));\n"
        oracle = self.repo.root / 'tests/value.test.mjs'
        oracle.write_text(script, encoding='utf-8')
        contract = self.repo.root / self.repo.contract
        content = contract.read_text().replace('tests/test_value.py', 'tests/value.test.mjs')
        content = content.replace('python -m unittest tests/value.test.mjs', 'node --test tests/value.test.mjs')
        content = content.replace(hashlib.sha256(self.repo.oracle.encode()).hexdigest(),
                                  hashlib.sha256(script.encode()).hexdigest())
        contract.write_text(content)
        self.repo.approved = self.repo.commit('approve Node oracle')
        self.repo.start()
        self.repo.integrate()
        result = self.repo.act('finish')
        self.assertEqual(result['task']['status'], 'done')
        self.assertEqual(gate.validate_snapshot(self.repo.root, 'main'), [])

    def test_closing_commit_cannot_include_unverified_code_changes(self):
        self.repo.start()
        self.repo.integrate()
        base = self.repo.git('rev-parse', 'HEAD')
        self.repo.act('finish')
        self.repo.git('reset', '--soft', 'HEAD^')
        (self.repo.root / 'src/value.py').write_text('def value():\n return 8\n')
        self.repo.commit('mix closure with changed product')
        self.assertTrue(gate.validate_range(self.repo.root, base, 'main'))

    def test_done_remains_historical_after_later_product_changes(self):
        self.repo.start()
        self.repo.integrate()
        self.repo.act('finish')
        (self.repo.root / 'src/value.py').write_text('def value():\n return 8\n')
        self.repo.commit('later product revision')
        self.assertEqual(gate.validate_snapshot(self.repo.root, 'main'), [])

    def test_malformed_node_is_a_finding_without_a_traceback(self):
        self.repo.act('create')
        path = self.repo.root / 'knowledge/tasks/TASK-001.md'
        path.write_text(path.read_text().replace("status: 'backlog'", "status: ['done']"))
        self.repo.commit('invalid status type')
        self.assertTrue(gate.validate_snapshot(self.repo.root, 'main'))


if __name__ == '__main__':
    unittest.main()
