"""Fresh single-path projection reads against real Git object states."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.test_fixture_preparation import configure_git

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import task_git as journal
from task_model import TaskError
from traceability_git import _Projection


class TraceProjectionFreshRead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area = tempfile.TemporaryDirectory(prefix='kdd-projection-base-')
        cls.addClassCleanup(cls.area.cleanup)
        cls.env = dict(os.environ, PYTHONUTF8='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_CONFIG_NOSYSTEM='1')
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
            cls.env.pop(key, None)
        cls.base = Path(cls.area.name) / 'base'
        cls.ref = cls.prepare(cls.base, 'sha1')

    @classmethod
    def git(cls, root, *args, input=None):
        return subprocess.run(['git', '--literal-pathspecs', '-C', str(root), *args],
            env=cls.env, input=input, capture_output=True, timeout=30, check=True).stdout

    @classmethod
    def prepare(cls, root, algorithm):
        root.mkdir()
        cls.git(root, 'init', '-q', '-b', 'main', '--object-format=' + algorithm)
        configure_git(root, {'user.name': 'Projection fixture', 'user.email': 'fixture@example.invalid',
            'core.autocrlf': 'false', 'maintenance.autoDetach': 'false', 'gc.autoDetach': 'false',
            'commit.gpgsign': 'false'}, ephemeral=True)
        (root / 'regular.txt').write_bytes(b'first\r\nsecond\rthird\n')
        (root / 'empty.txt').write_bytes(b'')
        (root / 'literal \u00f1 name.txt').write_bytes('caf\u00e9\n'.encode())
        (root / 'invalid.txt').write_bytes(b'\xffinvalid utf8\n')
        (root / 'directory').mkdir(); (root / 'directory/file.txt').write_bytes(b'nested\n')
        cls.git(root, 'add', '-A'); cls.git(root, 'commit', '-qm', 'Reviewed object fixture')
        return cls.git(root, 'rev-parse', 'HEAD').decode('ascii').strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-projection-case-')
        self.addCleanup(self.temp.cleanup)
        self.area_path = Path(self.temp.name)
        self.root = self.area_path / 'repo'
        shutil.copytree(self.base, self.root)
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)

    def projection(self, root=None, ref=None):
        return _Projection(root or self.root, ref or self.ref, 'unused-manifest.json')

    def test_regular_values_use_one_real_git_process_in_each_native_format(self):
        counts = []
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm):
                root = self.root if algorithm == 'sha1' else self.area_path / 'sha256'
                ref = self.ref if algorithm == 'sha1' else self.prepare(root, algorithm)
                projection = self.projection(root, ref)
                before = self.git(root, 'ls-files', '--stage', '-z')
                trace = self.area_path / (algorithm + '.jsonl')
                with journal.object_cache():
                    self.assertTrue(journal._native_oid(root, ref))
                    with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
                        self.assertEqual(projection.blob(ref, 'regular.txt'), 'first\nsecond\nthird\n')
                    self.assertEqual(projection.blob(ref, 'empty.txt'), '')
                    self.assertEqual(projection.blob(ref, 'literal \u00f1 name.txt'), 'caf\u00e9\n')
                starts = [e['argv'] for line in trace.read_text(encoding='utf-8-sig').splitlines()
                          if (e := json.loads(line)).get('event') == 'start']
                self.assertTrue(starts, 'the reader must execute real Git')
                counts.append((algorithm, len(starts), starts))
                self.assertEqual(self.git(root, 'ls-files', '--stage', '-z'), before)
        for algorithm, count, starts in counts:
            with self.subTest(process_budget=algorithm):
                self.assertLessEqual(count, 1, starts)

    def test_late_replacement_is_checked_when_the_new_path_is_requested(self):
        projection = self.projection()
        with journal.object_cache():
            self.assertEqual(projection.blob(self.ref, 'regular.txt'), 'first\nsecond\nthird\n')
            oid = self.git(self.root, 'rev-parse', self.ref + ':empty.txt').decode().strip()
            self.git(self.root, 'update-index', '--cacheinfo', '120000,' + oid + ',empty.txt')
            tree = self.git(self.root, 'write-tree').decode().strip()
            replacement = self.git(self.root, 'commit-tree', tree, '-m', 'Synthetic replacement').decode().strip()
            self.git(self.root, 'replace', self.ref, replacement)
            self.assertTrue(self.git(self.root, 'ls-tree', self.ref, '--', 'empty.txt').startswith(b'120000'))
            with self.assertRaisesRegex(ValueError, 'expected a regular Git blob: empty.txt'):
                projection.blob(self.ref, 'empty.txt')
            self.assertNotIn((self.ref, 'empty.txt'), projection.objects)
            self.git(self.root, 'replace', '-d', self.ref)
            self.assertEqual(projection.blob(self.ref, 'empty.txt'), '')

    def test_errors_and_restored_objects_do_not_cache_a_partial_success(self):
        projection = self.projection()
        with self.assertRaisesRegex(ValueError, 'missing regular Git file: absent.txt'):
            projection.blob(self.ref, 'absent.txt')
        with self.assertRaisesRegex(ValueError, 'expected a regular Git blob: directory'):
            projection.blob(self.ref, 'directory')
        with self.assertRaises((TaskError, UnicodeError)):
            projection.blob(self.ref, 'invalid.txt')
        name = 'literal \u00f1 name.txt'
        oid = self.git(self.root, 'rev-parse', self.ref + ':' + name).decode().strip()
        path = (self.root / '.git/objects' / oid[:2] / oid[2:]).resolve()
        self.assertTrue(path.is_relative_to((self.root / '.git/objects').resolve()))
        content = path.read_bytes(); digest = hashlib.sha256(content).hexdigest()
        path.chmod(stat.S_IREAD | stat.S_IWRITE); path.write_bytes(b'corrupt object\n')
        with self.assertRaises(TaskError): projection.blob(self.ref, name)
        self.assertNotIn((self.ref, name), projection.objects)
        path.write_bytes(content)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertEqual(projection.blob(self.ref, name), 'caf\u00e9\n')
        for unavailable in (False, None):
            with self.subTest(metadata_fallback=repr(unavailable)):
                with patch.object(journal, '_read_metadata', return_value=unavailable) as protocol:
                    fresh = self.projection()
                    self.assertEqual(fresh.blob(self.ref, 'empty.txt'), '')
                    protocol.assert_called_once()


if __name__ == '__main__':
    unittest.main()
