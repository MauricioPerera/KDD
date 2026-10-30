"""Real mutable refs, object formats, regular modes and bounded cached reads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import task_git as journal
from task_model import TaskError


class GitReaderRefCache(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-reader-cache-')
        self.addCleanup(self.area.cleanup)
        self.base = Path(self.area.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME='Git reader fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
            GIT_COMMITTER_NAME='Git reader fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
            self.env.pop(key, None)
        self.root, self.refs = self.repository('repo space-\u00f1')
        self.alias = 'f' * 64
        self.move(self.alias, self.refs['a'])

    def git(self, root, *argv, text=None):
        return subprocess.check_output(['git', '-C', str(root), *argv],
            input=text.encode('utf-8') if text is not None else None, env=self.env,
            stderr=subprocess.PIPE, timeout=30).decode('utf-8').strip()

    def repository(self, name, algorithm='sha1'):
        root = self.base / name
        root.mkdir()
        self.git(root, 'init', '-q', '-b', 'main', '--object-format=' + algorithm)
        for key in ('maintenance.autoDetach', 'gc.autoDetach'):
            self.git(root, 'config', key, 'false')
        one = self.git(root, 'hash-object', '-w', '--stdin', text='before\n')
        two = self.git(root, 'hash-object', '-w', '--stdin', text='after\n')
        a_tree = self.git(root, 'mktree', text='100644 blob ' + one + '\tfile.txt\n')
        b_tree = self.git(root, 'mktree', text='100644 blob ' + two + '\tfile.txt\n100644 blob ' + two + '\tnew.txt\n')
        link_tree = self.git(root, 'mktree', text='120000 blob ' + two + '\tfile.txt\n')
        empty = self.git(root, 'mktree', text='')
        a = self.git(root, 'commit-tree', a_tree, '-m', 'fixture A')
        b = self.git(root, 'commit-tree', b_tree, '-p', a, '-m', 'fixture B')
        link = self.git(root, 'commit-tree', link_tree, '-p', b, '-m', 'link mode')
        missing = self.git(root, 'commit-tree', empty, '-p', b, '-m', 'missing file')
        self.git(root, 'update-ref', 'refs/heads/main', b)
        return root, dict(a=a, b=b, link=link, missing=missing)

    def move(self, alias, revision, root=None):
        self.git(root or self.root, 'update-ref', 'refs/heads/' + alias, revision)

    def test_hex_alias_commit_is_resolved_again_within_operation(self):
        with journal.object_cache():
            self.assertEqual(journal.commit_sha(self.root, self.alias), self.refs['a'])
            self.move(self.alias, self.refs['b'])
            self.assertEqual(journal.commit_sha(self.root, self.alias), self.refs['b'])

    def test_hex_alias_blob_is_fresh_within_operation(self):
        with journal.object_cache():
            self.assertEqual(journal.blob(self.root, self.alias, 'file.txt'), 'before\n')
            self.move(self.alias, self.refs['b'])
            self.assertEqual(journal.blob(self.root, self.alias, 'file.txt'), 'after\n')

    def test_hex_alias_batch_blobs_use_current_revision(self):
        with journal.object_cache():
            self.assertEqual(journal.blobs(self.root, self.alias, ['file.txt']), {'file.txt': 'before\n'})
            self.move(self.alias, self.refs['b'])
            self.assertEqual(journal.blobs(self.root, self.alias, ['file.txt', 'new.txt']),
                             {'file.txt': 'after\n', 'new.txt': 'after\n'})

    def test_hex_alias_paths_are_fresh_within_operation(self):
        with journal.object_cache():
            self.assertEqual(journal.paths(self.root, self.alias, '.'), ['file.txt'])
            self.move(self.alias, self.refs['b'])
            self.assertEqual(journal.paths(self.root, self.alias, '.'), ['file.txt', 'new.txt'])

    def test_hex_alias_regular_proof_cannot_hide_current_symlink_mode(self):
        with journal.object_cache():
            journal._committed_paths(self.root, self.alias, ['file.txt'])
            self.move(self.alias, self.refs['link'])
            with self.assertRaisesRegex(TaskError, 'TASK_PATH'):
                journal._committed_paths(self.root, self.alias, ['file.txt'])

    def test_hex_alias_regular_proof_cannot_hide_missing_current_file(self):
        with journal.object_cache():
            journal._committed_paths(self.root, self.alias, ['file.txt'])
            self.move(self.alias, self.refs['missing'])
            with self.assertRaisesRegex(TaskError, 'TASK_PATH'):
                journal._committed_paths(self.root, self.alias, ['file.txt'])

    def test_ordinary_symbolic_ref_preserves_fresh_reads(self):
        self.move('readers', self.refs['a'])
        with journal.object_cache():
            self.assertEqual(journal.commit_sha(self.root, 'readers'), self.refs['a'])
            self.assertEqual(journal.blob(self.root, 'readers', 'file.txt'), 'before\n')
            self.assertEqual(journal.paths(self.root, 'readers', '.'), ['file.txt'])
            journal._committed_paths(self.root, 'readers', ['file.txt'])
            self.move('readers', self.refs['b'])
            self.assertEqual(journal.commit_sha(self.root, 'readers'), self.refs['b'])
            self.assertEqual(journal.blob(self.root, 'readers', 'file.txt'), 'after\n')
            self.assertEqual(journal.paths(self.root, 'readers', '.'), ['file.txt', 'new.txt'])

    def test_sha256_repository_treats_sha1_width_alias_as_mutable(self):
        root, refs = self.repository('sha256', algorithm='sha256')
        alias = 'e' * 40
        self.move(alias, refs['a'], root)
        with journal.object_cache():
            self.assertEqual(journal.commit_sha(root, alias), refs['a'])
            self.assertEqual(journal.blob(root, alias, 'file.txt'), 'before\n')
            self.assertEqual(journal.paths(root, alias, '.'), ['file.txt'])
            journal._committed_paths(root, alias, ['file.txt'])
            self.move(alias, refs['link'], root)
            self.assertEqual(journal.commit_sha(root, alias), refs['link'])
            self.assertEqual(journal.blob(root, alias, 'file.txt'), 'after\n')
            with self.assertRaisesRegex(TaskError, 'TASK_PATH'):
                journal._committed_paths(root, alias, ['file.txt'])

    def test_immutable_oid_reads_are_bounded_by_actual_trace2(self):
        trace = self.base / 'trace.jsonl'
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}), journal.object_cache():
            for _ in range(12):
                self.assertEqual(journal.commit_sha(self.root, self.refs['b']), self.refs['b'])
                self.assertEqual(journal.blob(self.root, self.refs['b'], 'file.txt'), 'after\n')
                self.assertEqual(journal.paths(self.root, self.refs['b'], '.'), ['file.txt', 'new.txt'])
                journal._committed_paths(self.root, self.refs['b'], ['file.txt'])
        starts = [json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()
                  if json.loads(line).get('event') == 'start']
        self.assertTrue(starts, 'real Git Trace2 evidence is mandatory')
        self.assertLessEqual(len(starts), 5, 'repeated OID reads must retain bounded Git work')

    def test_empty_batch_does_not_require_a_resolvable_ref(self):
        with journal.object_cache():
            self.assertEqual(journal.blobs(self.root, 'missing-ref', []), {})

    def test_operation_exception_discards_hex_alias_values(self):
        with self.assertRaisesRegex(RuntimeError, 'abort'), journal.object_cache():
            self.assertEqual(journal.blob(self.root, self.alias, 'file.txt'), 'before\n')
            raise RuntimeError('abort')
        self.move(self.alias, self.refs['b'])
        with journal.object_cache():
            self.assertEqual(journal.blob(self.root, self.alias, 'file.txt'), 'after\n')

    def test_repositories_do_not_share_alias_values(self):
        other, refs = self.repository('other')
        self.move(self.alias, refs['b'], other)
        with journal.object_cache():
            self.assertEqual(journal.blob(self.root, self.alias, 'file.txt'), 'before\n')
            self.assertEqual(journal.blob(other, self.alias, 'file.txt'), 'after\n')

    def test_missing_alias_is_retried_after_real_ref_creation(self):
        alias = 'd' * 64
        with journal.object_cache():
            with self.assertRaises(TaskError):
                journal.commit_sha(self.root, alias)
            self.move(alias, self.refs['a'])
            self.assertEqual(journal.commit_sha(self.root, alias), self.refs['a'])

    def test_without_cache_all_hex_alias_queries_are_fresh(self):
        self.assertEqual(journal.blob(self.root, self.alias, 'file.txt'), 'before\n')
        self.move(self.alias, self.refs['b'])
        self.assertEqual(journal.blob(self.root, self.alias, 'file.txt'), 'after\n')


if __name__ == '__main__':
    unittest.main()
