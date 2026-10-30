"""Frozen oracle for auditing actual committed task transitions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_tasks as gate
import task_model as model
import tests.test_task_git as fixtures


class TaskValidationTests(unittest.TestCase):
    def setUp(self):
        self.repo = fixtures.Repository()
        self.addCleanup(self.repo.close)

    def test_empty_project_and_valid_lifecycle(self):
        self.assertEqual(gate.validate_snapshot(self.repo.root, 'main'), [])
        base = self.repo.approved
        self.repo.start()
        self.repo.integrate()
        self.repo.act('finish')
        self.assertEqual(gate.validate_snapshot(self.repo.root, 'main'), [])
        self.assertEqual(gate.validate_range(self.repo.root, base, 'main'), [])

    def test_intermediate_illegal_commit_cannot_hide_behind_valid_final_state(self):
        self.repo.act('create')
        base = self.repo.git('rev-parse', 'HEAD')
        file = self.repo.root / 'knowledge/tasks/TASK-001.md'
        data, body = model.parse_task(file.read_text(), file.name)
        original = dict(data)
        data.update(status='in_progress', assignee='owner', approved_ref=self.repo.approved,
                    branch_base=base)
        file.write_text(model.render_task(data, body), encoding='utf-8')
        self.repo.commit('illegal skip')
        file.write_text(model.render_task(original, body), encoding='utf-8')
        self.repo.commit('hide illegal transition')
        self.assertTrue(gate.validate_range(self.repo.root, base, 'main'))

    def test_deletion_is_rejected(self):
        self.repo.act('create')
        base = self.repo.git('rev-parse', 'HEAD')
        (self.repo.root / 'knowledge/tasks/TASK-001.md').unlink()
        self.repo.commit('delete task')
        self.assertTrue(gate.validate_range(self.repo.root, base, 'main'))

    def test_tampered_evidence_is_rejected(self):
        self.repo.start()
        self.repo.integrate()
        result = self.repo.act('finish')
        evidence = self.repo.root / result['task']['evidence']
        evidence.write_text('{}\n')
        self.repo.commit('tamper with evidence')
        self.assertTrue(gate.validate_snapshot(self.repo.root, 'main'))

    def test_checkout_changes_do_not_change_committed_snapshot(self):
        self.repo.act('create')
        file = self.repo.root / 'knowledge/tasks/TASK-001.md'
        file.write_text('uncommitted broken node')
        self.assertEqual(gate.validate_snapshot(self.repo.root, 'main'), [])

    def test_invalid_refs_fail_closed(self):
        self.assertTrue(gate.validate_range(self.repo.root, 'missing-ref', 'main'))


if __name__ == '__main__':
    unittest.main()
