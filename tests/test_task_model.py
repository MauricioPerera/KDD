"""Frozen oracle for Task nodes and legal lifecycle transitions."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import task_model as model
import validate_okf


def sample():
    return model.new_task('TASK-001', 'Validate users', 'Validate user input',
                          'knowledge/contracts/users.md', [])


class TaskModelTests(unittest.TestCase):
    def test_task_is_a_supported_okf_node(self):
        self.assertIn('Task', validate_okf.VALID_TYPES)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'contracts').mkdir()
            (root / 'tasks').mkdir()
            (root / 'index.md').write_text('[Tasks](tasks/)\n[Contracts](contracts/)\n')
            (root / 'contracts/users.md').write_text(
                "---\ntype: 'Concept'\ntitle: 'Users'\ndescription: 'Users'\ntags: ['users']\n---\n")
            (root / 'tasks/TASK-001.md').write_text(model.render_task(sample()), encoding='utf-8')
            self.assertFalse([f for f in validate_okf.validate_okf(tmp) if f.level == 'ERROR'])

    def test_round_trip_preserves_notes_and_quoted_text(self):
        data = sample()
        data['title'] = "O'Neil, user"
        body = '\n# Notes\n\nKeep this decision.\n'
        parsed, notes = model.parse_task(model.render_task(data, body), 'TASK-001.md')
        self.assertEqual(parsed, data)
        self.assertIn('Keep this decision.', notes)

    def test_duplicate_metadata_is_rejected(self):
        text = model.render_task(sample()).replace('status:', 'status: done\nstatus:', 1)
        with self.assertRaises(model.TaskError):
            model.parse_task(text, 'TASK-001.md')

    def test_invalid_ids_paths_statuses_and_multiline_values_are_rejected(self):
        for key, value in [('task_id', '../TASK-001'), ('branch', 'main'),
                           ('contract', '../outside.md'), ('status', 'complete'),
                           ('title', 'A\nstatus: done'), ('approved_ref', 'HEAD'),
                           ('depends_on', ['TASK-001']), ('tags', ['UPPER'])]:
            with self.subTest(key=key):
                data = sample()
                data[key] = value
                self.assertTrue(model.validate_task(data))

    def test_filename_identity_is_checked(self):
        with self.assertRaises(model.TaskError):
            model.parse_task(model.render_task(sample()), 'TASK-002.md')

    def test_creation_must_start_in_backlog(self):
        data = sample()
        self.assertEqual(model.validate_transition(None, data), [])
        data['status'] = 'ready'
        data['approved_ref'] = 'a' * 40
        self.assertTrue(model.validate_transition(None, data))

    def test_lifecycle_and_block_resume(self):
        before = sample()
        for state in ['ready', 'in_progress', 'needs_human_input', 'ready', 'in_progress', 'done']:
            after = deepcopy(before)
            after.update(status=state, reason='Documented decision', approved_ref='a' * 40)
            if state in ('in_progress', 'needs_human_input', 'done') or before['branch_base']:
                after.update(assignee='owner', branch_base='b' * 40)
            if state == 'done':
                after.update(verified_ref='c' * 40,
                             evidence='docs/task-evidence/TASK-001-' + 'c' * 40 + '.json',
                             evidence_sha256='d' * 64)
            self.assertEqual(model.validate_transition(before, after), [])
            before = after

    def test_skip_delete_and_reopening_are_rejected(self):
        data = sample()
        after = deepcopy(data)
        after['status'] = 'done'
        self.assertTrue(model.validate_transition(data, after))
        self.assertTrue(model.validate_transition(data, None))

    def test_dependencies_must_be_completed_before_start(self):
        before = sample()
        before.update(status='ready', approved_ref='a' * 40, depends_on=['TASK-002'])
        after = dict(before, status='in_progress', assignee='owner', branch_base='b' * 40)
        self.assertTrue(model.validate_transition(before, after))
        self.assertEqual(model.validate_transition(before, after, {'TASK-002'}), [])

    def test_identity_and_approved_reference_cannot_drift(self):
        before = dict(sample(), status='ready', approved_ref='a' * 40)
        for key, value in [('contract', 'knowledge/contracts/other.md'),
                           ('approved_ref', 'b' * 40), ('depends_on', ['TASK-002'])]:
            after = dict(before, status='in_progress', assignee='owner', branch_base='c' * 40)
            after[key] = value
            self.assertTrue(model.validate_transition(before, after))

    def test_done_is_immutable(self):
        before = sample()
        before.update(status='done', assignee='owner', approved_ref='a' * 40,
                      branch_base='b' * 40, verified_ref='c' * 40,
                      evidence='docs/task-evidence/TASK-001-' + 'c' * 40 + '.json',
                      evidence_sha256='d' * 64)
        self.assertTrue(model.validate_transition(before, dict(before, reason='Rewrite history')))


if __name__ == '__main__':
    unittest.main()
