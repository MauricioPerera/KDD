"""Real Git merge DAGs for nested task import history."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_tasks
from tests.test_task_git import Repository


class TaskImportAncestryTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.addCleanup(self.repo.close)
        self.path = self.repo.root / 'knowledge/tasks/TASK-001.md'
        self.repo.git('branch', 'feature', self.repo.approved)
        self.repo.act('create')
        self.main_base = self.repo.git('rev-parse', 'HEAD')
        self.task = self.path.read_text(encoding='utf-8')
        self.repo.git('switch', '-q', 'feature')
        (self.repo.root / 'feature.txt').write_text('feature\n', encoding='utf-8')
        self.repo.commit('feature change before integration')
        self.bad = ''

    def illegal_then_restore(self, existed):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        invalid = self.task.replace("status: 'backlog'", "status: 'in_progress'")
        self.assertNotEqual(invalid, self.task)
        self.path.write_text(invalid, encoding='utf-8')
        self.bad = self.repo.commit('illegal task transition hidden by restoration')
        if existed:
            self.path.write_text(self.task, encoding='utf-8')
        else:
            self.path.unlink()
        self.repo.commit('restore task snapshot')

    def integrate(self, *, invalid_before=False, invalid_after=False):
        if invalid_before:
            self.illegal_then_restore(existed=False)
        self.repo.git('merge', '--no-ff', '-qm', 'integrate main as second parent', 'main')
        if invalid_after:
            self.illegal_then_restore(existed=True)
        source = self.repo.git('rev-parse', 'HEAD')
        self.repo.git('switch', '-q', 'main')
        self.repo.git('merge', '--no-ff', '-qm', 'publish feature with main integrated', 'feature')
        return source, self.repo.git('rev-parse', 'HEAD')

    def validate(self, head):
        return validate_tasks.validate_range(self.repo.root, self.main_base, head)

    def test_valid_import_with_main_on_source_second_parent(self):
        source, head = self.integrate()
        self.assertEqual(self.repo.git('merge-base', source, self.main_base), self.main_base)
        self.assertNotIn(self.main_base, self.repo.git('rev-list', '--first-parent', source).splitlines())
        self.assertEqual(self.validate(head), [])

    def test_cli_accepts_the_valid_nested_import_without_git_writes(self):
        _, head = self.integrate()
        before = (self.repo.git('status', '--porcelain=v1'), self.repo.git('show-ref'))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_tasks.py'),
            '--repo-root', str(self.repo.root), '--base-ref', self.main_base,
            '--head-ref', head], capture_output=True, text=True, encoding='utf-8',
            env=dict(os.environ, PYTHONUTF8='1'), timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, (self.repo.git('status', '--porcelain=v1'), self.repo.git('show-ref')))

    def test_hidden_invalid_transition_before_integrating_main_is_rejected(self):
        _, head = self.integrate(invalid_before=True)
        errors = self.validate(head)
        self.assertTrue(any(self.bad in item and 'TASK_' in item for item in errors), errors)
        self.assertFalse(any('TASK_BASELINE' in item for item in errors), errors)

    def test_hidden_invalid_transition_after_integrating_main_is_rejected(self):
        _, head = self.integrate(invalid_after=True)
        errors = self.validate(head)
        self.assertTrue(any(self.bad in item and 'TASK_' in item for item in errors), errors)
        self.assertFalse(any('TASK_BASELINE' in item for item in errors), errors)

    def test_merge_cannot_invent_task_content(self):
        self.repo.git('merge', '--no-ff', '-qm', 'integrate main as second parent', 'main')
        self.repo.git('switch', '-q', 'main')
        self.repo.git('merge', '--no-ff', '--no-commit', 'feature')
        self.path.write_text(self.task + '\nUnreviewed merge edit.\n', encoding='utf-8')
        head = self.repo.commit('tamper with task while publishing')
        errors = self.validate(head)
        self.assertTrue(any('TASK_IMPORT' in item for item in errors), errors)
        self.assertFalse(any('TASK_BASELINE' in item for item in errors), errors)

    def test_shallow_nested_history_is_rejected(self):
        _, head = self.integrate()
        area = tempfile.TemporaryDirectory(prefix='kdd-shallow-import-')
        self.addCleanup(area.cleanup)
        shallow = Path(area.name) / 'project'
        clone = subprocess.run(['git', 'clone', '--quiet', '--depth=3',
            self.repo.root.as_uri(), str(shallow)], capture_output=True,
            text=True, encoding='utf-8', timeout=120)
        self.assertEqual(clone.returncode, 0, clone.stdout + clone.stderr)
        check = subprocess.run(['git', '-C', str(shallow), 'rev-parse',
            '--is-shallow-repository'], capture_output=True, text=True,
            encoding='utf-8', timeout=30)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(check.stdout.strip(), 'true')
        errors = validate_tasks.validate_range(shallow, self.main_base, head)
        self.assertTrue(any('TASK_BASELINE' in item and 'complete history' in item
                            for item in errors), errors)

    def test_public_base_still_must_be_first_parent(self):
        source, head = self.integrate()
        errors = validate_tasks.validate_range(self.repo.root, source, head)
        self.assertTrue(any('TASK_BASELINE' in item for item in errors), errors)


if __name__ == '__main__':
    unittest.main()
