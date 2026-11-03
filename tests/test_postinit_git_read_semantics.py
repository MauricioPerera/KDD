"""Adversarial Git object controls for post-init read optimizations."""
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import task_git as journal
from task_model import TaskError


class GitObjectReadSemantics(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-object-semantics-')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Object control')
        self.git('config', 'user.email', 'object-control@example.invalid')
        self.git('config', 'gc.auto', '0')
        self.git('config', 'maintenance.auto', 'false')

    def git(self, *args, input=None):
        return subprocess.run(['git', '-C', str(self.root), *args], input=input,
                              text=True, encoding='utf-8', capture_output=True,
                              timeout=30, check=True).stdout.strip()

    def commit(self, first, second):
        (self.root / 'a.txt').write_text(first, encoding='utf-8')
        (self.root / 'b.txt').write_text(second, encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-qm', 'object fixture')
        return self.git('rev-parse', 'HEAD')

    def test_replacement_is_observed_by_a_later_object_read(self):
        original = self.commit('A1\n', 'A2\n')
        replacement = self.commit('B1\n', 'B2\n')
        with journal.object_cache():
            self.assertEqual(journal.blob(self.root, original, 'a.txt'), 'A1\n')
            self.git('replace', original, replacement)
            self.assertEqual(journal.blob(self.root, original, 'b.txt'), 'B2\n')

    def test_malformed_commit_does_not_pass_perimeter_identity_check(self):
        first = self.commit('one\n', 'two\n')
        second = self.commit('three\n', 'four\n')
        malformed = self.git('hash-object', '--literally', '-t', 'commit', '-w', '--stdin',
                             input='not a valid commit\n')
        with journal.object_cache():
            with self.assertRaises(TaskError):
                journal._perimeter_refs(self.root, (first, second, malformed))
            self.assertEqual(journal.commit_sha(self.root, first), first)

    def test_missing_commit_does_not_poison_a_later_valid_perimeter(self):
        first = self.commit('one\n', 'two\n')
        second = self.commit('three\n', 'four\n')
        missing = '0' * len(first)
        with journal.object_cache():
            with self.assertRaises(TaskError):
                journal._perimeter_refs(self.root, (first, second, missing))
            journal._perimeter_refs(self.root, (first, second))


if __name__ == '__main__':
    unittest.main()
