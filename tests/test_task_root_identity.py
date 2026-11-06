"""Real repository identity changes and bounded root canonicalization."""
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_fixture_preparation import configure_git, directory_alias

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import task_git as journal
from task_model import TaskError


class RootIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-root-identity-')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        PYTHONUTF8='1')
        self.root, self.ref = self.repo('first')

    def git(self, root, *args):
        return subprocess.run(['git', '-C', str(root), *args], env=self.env,
            capture_output=True, text=True, encoding='utf-8', check=True, timeout=30).stdout.strip()

    def repo(self, name, value='original payload\n'):
        root = self.area / name
        root.mkdir()
        self.git(root, 'init', '-q', '-b', 'main')
        configure_git(root, {'user.name': 'Root fixture', 'user.email': 'root@example.invalid',
                            'core.autocrlf': 'false'}, ephemeral=True)
        (root / 'value.txt').write_text(value, encoding='utf-8')
        self.git(root, 'add', 'value.txt')
        self.git(root, 'commit', '-qm', 'Synthetic identity baseline')
        return root, self.git(root, 'rev-parse', 'HEAD')

    def clone_without_blob(self):
        root = self.area / 'independent'
        self.git(self.area, 'clone', '-q', '--no-hardlinks', str(self.root), str(root))
        oid = self.git(root, 'rev-parse', self.ref + ':value.txt')
        objects = (root / '.git/objects').resolve()
        path = (objects / oid[:2] / oid[2:]).resolve()
        self.assertTrue(path.is_relative_to(objects))
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_nlink, 1)
        path.chmod(stat.S_IREAD | stat.S_IWRITE)
        path.unlink()
        return root

    @staticmethod
    def remove_alias(path):
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            path.rmdir()

    def test_regular_root_does_not_resolve_for_each_key(self):
        original = Path.resolve
        calls = []
        def resolve(path, *args, **kwargs):
            if path.absolute() == self.root.absolute():
                calls.append(str(path))
            return original(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve), journal.object_cache():
            keys = [journal._key(self.root, 'blob', self.ref, 'value.txt') for _ in range(100)]
        self.assertEqual(len(set(keys)), 1)
        self.assertLessEqual(len(calls), 2, 'Repeated canonicalizations: %d' % len(calls))

    def test_path_string_and_native_alias_select_the_same_root(self):
        alias = self.area / 'alias'
        directory_alias(alias, self.root, self.area)
        self.addCleanup(self.remove_alias, alias)
        with journal.object_cache():
            expected = journal._key(self.root, 'blob', self.ref, 'value.txt')
            self.assertEqual(journal._key(str(self.root), 'blob', self.ref, 'value.txt'), expected)
            self.assertEqual(journal._key(alias, 'blob', self.ref, 'value.txt'), expected)

    def test_distinct_repository_with_same_oid_does_not_reuse_content(self):
        other = self.clone_without_blob()
        with journal.object_cache():
            self.assertEqual(journal.blob(self.root, self.ref, 'value.txt'), 'original payload\n')
            with self.assertRaises(TaskError):
                journal.blob(other, self.ref, 'value.txt')

    def test_replaced_directory_at_same_path_is_not_the_previous_repository(self):
        other = self.clone_without_blob()
        with journal.object_cache():
            self.assertEqual(journal.blob(self.root, self.ref, 'value.txt'), 'original payload\n')
            self.root.rename(self.area / 'moved-original')
            other.rename(self.root)
            with self.assertRaises(TaskError):
                journal.blob(self.root, self.ref, 'value.txt')

    def test_redirected_native_alias_observes_the_new_repository(self):
        other = self.clone_without_blob()
        alias = self.area / 'moving-alias'
        directory_alias(alias, self.root, self.area)
        self.addCleanup(self.remove_alias, alias)
        with journal.object_cache():
            self.assertEqual(journal.blob(alias, self.ref, 'value.txt'), 'original payload\n')
            self.remove_alias(alias)
            directory_alias(alias, other, self.area)
            with self.assertRaises(TaskError):
                journal.blob(alias, self.ref, 'value.txt')

    def test_relative_root_observes_changed_working_directory(self):
        first = self.area / 'left'; first.mkdir()
        second = self.area / 'right'; second.mkdir()
        self.root.rename(first / 'repo')
        other = second / 'repo'; other.mkdir()
        previous = Path.cwd()
        try:
            with journal.object_cache():
                os.chdir(first)
                left = journal._key(Path('repo'), 'blob', self.ref, 'value.txt')
                os.chdir(second)
                right = journal._key(Path('repo'), 'blob', self.ref, 'value.txt')
                self.assertNotEqual(left, right)
        finally:
            os.chdir(previous)

    def test_namespace_parts_remain_distinct(self):
        keys = [journal._key(self.root, kind, revision, path) for kind, revision, path in
                [('blob', self.ref, 'value.txt'), ('commit', self.ref, 'value.txt'),
                 ('blob', 'main', 'value.txt'), ('blob', self.ref, 'other.txt')]]
        self.assertEqual(len(set(keys)), 4)

    def test_missing_or_non_directory_root_keeps_path_fallback(self):
        for root in (self.area / 'missing', self.root / 'value.txt'):
            with self.subTest(root=str(root)):
                self.assertEqual(journal._key(root, 'blob', self.ref)[0], str(root.resolve()))

    def test_zero_inode_uses_the_compatible_fallback(self):
        original = os.stat
        def stat_without_identity(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if isinstance(path, (str, bytes, os.PathLike)) and Path(path).absolute() == self.root:
                fields = list(result); fields[1] = 0; fields[2] = 0
                return os.stat_result(fields)
            return result
        expected = str(self.root.resolve())
        with patch.object(os, 'stat', stat_without_identity):
            self.assertEqual(journal._key(self.root, 'blob', self.ref)[0], expected)


if __name__ == '__main__':
    unittest.main()
