"""Frozen oracle for publishing a preserved task journal through a Git merge."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import task_git as journal
from validate_tasks import validate_range, validate_snapshot
from tests.test_task_git import Repository


class TaskPublicationTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.addCleanup(self.repo.close)
        self.path = 'knowledge/tasks/TASK-001.md'

    def complete(self):
        self.repo.start()
        self.repo.act('block', reason='Need a decision')
        self.repo.act('resume', reason='Decision recorded')
        self.repo.act('start', assignee='developer')
        self.repo.integrate()
        return self.repo.act('finish')

    def rewind_main(self, base):
        # This repository is disposable; the source commits stay on delivery.
        self.repo.git('branch', 'delivery', 'main')
        self.repo.git('switch', '-q', '--detach', base)
        self.repo.git('branch', '-f', 'main', base)
        self.repo.git('switch', '-q', 'main')

    def publish(self, base=None):
        self.rewind_main(base or self.repo.approved)
        self.repo.git('merge', '--no-ff', '-qm', 'publish journal', 'delivery')
        return self.repo.git('rev-parse', 'HEAD')

    def findings(self):
        return validate_range(self.repo.root, self.repo.approved, 'main')

    def test_completed_journal_preserves_transitions_and_original_proof(self):
        closed = self.complete()
        entries = journal.history(self.repo.root, 'TASK-001')
        self.assertEqual([e['status'] for e in entries], [
            'backlog', 'ready', 'in_progress', 'needs_human_input',
            'ready', 'in_progress', 'done'])
        merge = self.publish()
        self.assertEqual(self.findings(), [])
        self.assertEqual(journal.history(self.repo.root, 'TASK-001'), entries)
        self.assertNotIn(merge, [e['commit'] for e in entries])
        self.assertEqual(journal.read_tasks(self.repo.root)['TASK-001'], closed['task'])
        self.assertNotEqual(closed['task']['verified_ref'], self.repo.git('rev-parse', 'HEAD^'))

    def test_partial_journal_is_imported_without_inventing_a_transition(self):
        self.repo.start()
        entries = journal.history(self.repo.root, 'TASK-001')
        self.publish()
        self.assertEqual(self.findings(), [])
        self.assertEqual(journal.history(self.repo.root, 'TASK-001'), entries)

    def test_updates_to_an_existing_task_can_be_imported(self):
        base = self.repo.start()['commit']
        blocked = self.repo.act('block', reason='Decision required')
        self.publish(base)
        self.assertEqual(self.findings(), [])
        self.assertEqual(journal.history(self.repo.root, 'TASK-001')[-1]['commit'], blocked['commit'])

    def test_invalid_intermediate_source_commit_cannot_hide_behind_valid_tip(self):
        self.repo.start()
        path = self.repo.root / self.path
        original = path.read_text(encoding='utf-8')
        path.write_text(original.replace("status: 'in_progress'", "status: 'ready'"), encoding='utf-8')
        bad = self.repo.commit('illegal backwards transition')
        path.write_text(original, encoding='utf-8')
        self.repo.commit('restore final state')
        self.assertEqual(validate_snapshot(self.repo.root), [])
        self.publish()
        self.assertTrue(any(bad in error and 'TASK_TRANSITION' in error for error in self.findings()))

    def test_squashed_closed_snapshot_is_rejected_even_with_evidence(self):
        self.complete()
        tree = self.repo.git('rev-parse', 'HEAD^{tree}')
        fake = self.repo.git('commit-tree', tree, '-p', self.repo.approved, '-m', 'squashed journal')
        self.repo.git('branch', 'squashed', fake)
        self.rewind_main(self.repo.approved)
        self.repo.git('merge', '--no-ff', '-qm', 'publish squash', 'squashed')
        self.assertTrue(any('TASK_CREATE' in error or 'TASK_CLOSURE' in error for error in self.findings()))

    def test_merge_cannot_modify_source_task_body(self):
        self.repo.start()
        self.rewind_main(self.repo.approved)
        self.repo.git('merge', '--no-ff', '--no-commit', 'delivery')
        with (self.repo.root / self.path).open('a', encoding='utf-8') as stream:
            stream.write('\nUnreviewed merge edit.\n')
        self.repo.commit('modify task during publication')
        self.assertTrue(any('TASK_IMPORT' in error for error in self.findings()))

    def test_merge_cannot_overwrite_concurrent_main_task_changes(self):
        base = self.repo.start()['commit']
        self.repo.act('block', reason='Source decision')
        source = (self.repo.root / self.path).read_text(encoding='utf-8')
        self.rewind_main(base)
        self.repo.act('block', reason='Target decision')
        with self.assertRaises(subprocess.CalledProcessError):
            self.repo.git('merge', '--no-ff', '--no-commit', 'delivery')
        (self.repo.root / self.path).write_text(source, encoding='utf-8')
        self.repo.commit('resolve by overwriting target task')
        self.assertTrue(any('TASK_IMPORT' in error for error in self.findings()))

    def test_implementation_merge_does_not_duplicate_task_history(self):
        self.repo.start()
        entries = journal.history(self.repo.root, 'TASK-001')
        self.repo.integrate()
        self.assertEqual(self.findings(), [])
        self.assertEqual(journal.history(self.repo.root, 'TASK-001'), entries)

    def test_baseline_must_remain_on_first_parent_history(self):
        self.repo.start()
        source = self.repo.git('rev-parse', 'HEAD')
        self.publish()
        errors = validate_range(self.repo.root, source, 'main')
        self.assertTrue(any('TASK_BASELINE' in error for error in errors))

    def test_nested_publication_is_audited_and_keeps_original_commits(self):
        self.repo.start()
        entries = journal.history(self.repo.root, 'TASK-001')
        self.publish()
        self.repo.git('branch', '-m', 'delivery', 'first-delivery')
        self.publish()
        self.assertEqual(self.findings(), [])
        self.assertEqual(journal.history(self.repo.root, 'TASK-001'), entries)


if __name__ == '__main__':
    unittest.main()
