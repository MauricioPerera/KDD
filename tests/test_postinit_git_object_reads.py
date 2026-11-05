"""Real Git evidence for bounded reads in the initialized-project workload."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from tests import test_traceability_model as support
import task_git as journal
from task_model import TaskError
from traceability_git import build_trace
from validate_tasks import validate_range, validate_snapshot


class ClosedTaskReadCost(support.RepositoryFixture):
    def trace(self, operation):
        trace = Path(self.temp.name) / 'git-events.jsonl'
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
            value = operation()
        self.assertTrue(trace.is_file(), 'Git Trace2 must record the real operation')
        events = [json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()]
        return value, events

    def test_closed_task_full_audit_uses_bounded_git_processes(self):
        task = journal.read_tasks(self.root, self.refs['closed'])['TASK-001']
        before = (support.git(self.root, 'rev-parse', 'HEAD'),
                  support.git(self.root, 'status', '--porcelain=v1'),
                  support.git(self.root, 'show-ref'), (self.root / '.git/index').read_bytes())

        def operation():
            with journal.object_cache():
                snapshot = validate_snapshot(self.root, 'main')
                history = validate_range(self.root, task['branch_base'], 'main')
                trace = build_trace(self.root, 'main', 'quality/traceability.json',
                                    require_verified=True)
            return snapshot, history, trace

        (snapshot, history, report), events = self.trace(operation)
        self.assertEqual(snapshot, [])
        self.assertEqual(history, [])
        self.assertTrue(report['complete'], report)
        self.assertEqual(report['requirements'][0]['links'][0]['task_id'], 'TASK-001')
        starts = [event for event in events if event.get('event') == 'start']
        self.assertLessEqual(len(starts), 62, 'real Git starts: %d' % len(starts))
        after = (support.git(self.root, 'rev-parse', 'HEAD'),
                 support.git(self.root, 'status', '--porcelain=v1'),
                 support.git(self.root, 'show-ref'), (self.root / '.git/index').read_bytes())
        self.assertEqual(after, before)

    def test_symbolic_branch_move_is_observed_within_one_operation(self):
        name = 'src/value.py'
        with journal.object_cache():
            closed = journal.blob(self.root, 'main', name)
            support.git(self.root, 'update-ref', 'refs/heads/main', self.refs['approved'])
            approved = journal.blob(self.root, 'main', name)
        self.assertIn('def value', closed)
        self.assertIn('NotImplementedError', approved)
        self.assertNotEqual(closed, approved)

    def test_git_children_finish_after_exception_leaves_scope(self):
        def operation():
            with self.assertRaisesRegex(RuntimeError, 'synthetic stop'):
                with journal.object_cache():
                    self.assertIn('def value', journal.blob(self.root, 'main', 'src/value.py'))
                    raise RuntimeError('synthetic stop')
        _, events = self.trace(operation)
        starts = {event['sid'] for event in events if event.get('event') == 'start'
                  and 'cat-file' in event.get('argv', [])}
        exits = {event['sid'] for event in events if event.get('event') == 'exit'}
        self.assertTrue(starts, 'the operation must start real Git object readers')
        self.assertFalse(starts - exits, 'Git readers remained alive after scope exit')


class IsolatedObjectIntegrity(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-object-read-integrity-')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name) / 'project'
        self.root.mkdir()
        support.git(self.root, 'init', '-q', '-b', 'main')
        support.git(self.root, 'config', 'user.name', 'Read integrity')
        support.git(self.root, 'config', 'user.email', 'read-integrity@example.invalid')
        support.git(self.root, 'config', 'gc.auto', '0')
        support.git(self.root, 'config', 'maintenance.auto', 'false')

    def commit_files(self, files):
        for name, content in files.items():
            support.write(self.root, name, content)
        support.git(self.root, 'add', '-A')
        support.git(self.root, 'commit', '-qm', 'fixture')
        return support.git(self.root, 'rev-parse', 'HEAD')

    def test_variable_size_blobs_preserve_framing_and_content(self):
        files = {'small.txt': 'first\nsecond\n', 'unicode.txt': 'cafe\u0301\n',
                 'large.txt': ('0123456789abcdef\n' * 65536)}
        ref = self.commit_files(files)
        with journal.object_cache():
            self.assertEqual(journal.blobs(self.root, ref, list(files)), files)
            self.assertEqual(journal.blob(self.root, ref, 'small.txt'), files['small.txt'])

    def test_missing_object_fails_and_failure_is_not_cached(self):
        content = 'independent loose object\n'
        ref = self.commit_files({'file.txt': content})
        oid = support.git(self.root, 'rev-parse', ref + ':file.txt')
        objects = (self.root / '.git/objects').resolve()
        obj = (objects / oid[:2] / oid[2:]).resolve()
        self.assertTrue(obj.is_relative_to(objects))
        self.assertTrue(obj.is_file(), 'the fixture requires a real loose Git object')
        obj.chmod(stat.S_IREAD | stat.S_IWRITE)
        obj.unlink()
        with journal.object_cache():
            with self.assertRaises(TaskError):
                journal.blob(self.root, ref, 'file.txt')
            self.assertEqual(support.git(self.root, 'hash-object', '-w', '--stdin', input=content), oid)
            self.assertEqual(journal.blob(self.root, ref, 'file.txt'), content)

    def test_corrupt_object_fails_and_does_not_poison_retry(self):
        content = 'real object integrity\n'
        ref = self.commit_files({'file.txt': content})
        oid = support.git(self.root, 'rev-parse', ref + ':file.txt')
        objects = (self.root / '.git/objects').resolve()
        obj = (objects / oid[:2] / oid[2:]).resolve()
        self.assertTrue(obj.is_relative_to(objects))
        self.assertTrue(obj.is_file(), 'the fixture requires a real loose Git object')
        original = obj.read_bytes()
        obj.chmod(stat.S_IREAD | stat.S_IWRITE)
        obj.write_bytes(b'corrupt compressed Git object')
        with journal.object_cache():
            with self.assertRaises(TaskError):
                journal.blob(self.root, ref, 'file.txt')
            obj.write_bytes(original)
            self.assertEqual(journal.blob(self.root, ref, 'file.txt'), content)

    def test_same_oid_in_another_repository_does_not_hide_missing_object(self):
        content = 'object must remain repository scoped\n'
        ref = self.commit_files({'file.txt': content})
        oid = support.git(self.root, 'rev-parse', ref + ':file.txt')
        other = Path(self.area.name) / 'independent-clone'
        support.git(Path(self.area.name), 'clone', '-q', '--no-hardlinks',
                    str(self.root), str(other))
        objects = (other / '.git/objects').resolve()
        obj = (objects / oid[:2] / oid[2:]).resolve()
        self.assertTrue(obj.is_relative_to(objects))
        self.assertTrue(obj.is_file(), 'the clone must have its own loose object')
        self.assertEqual(obj.stat().st_nlink, 1)
        obj.chmod(stat.S_IREAD | stat.S_IWRITE)
        obj.unlink()
        with journal.object_cache():
            self.assertEqual(journal.blob(self.root, ref, 'file.txt'), content)
            with self.assertRaises(TaskError):
                journal.blob(other, ref, 'file.txt')

    def test_sha256_repository_reads_real_blobs(self):
        other = Path(self.area.name) / 'sha256-project'
        other.mkdir()
        support.git(other, 'init', '-q', '-b', 'main', '--object-format=sha256')
        support.git(other, 'config', 'user.name', 'SHA256 fixture')
        support.git(other, 'config', 'user.email', 'sha256@example.invalid')
        support.git(other, 'config', 'gc.auto', '0')
        support.git(other, 'config', 'maintenance.auto', 'false')
        support.write(other, 'first.txt', 'sha256 first\n')
        support.write(other, 'second.txt', 'sha256 second\n')
        support.git(other, 'add', '-A')
        support.git(other, 'commit', '-qm', 'sha256 fixture')
        ref = support.git(other, 'rev-parse', 'HEAD')
        self.assertEqual(len(ref), 64)
        with journal.object_cache():
            self.assertEqual(journal.blobs(other, ref, ['first.txt', 'second.txt']),
                             {'first.txt': 'sha256 first\n', 'second.txt': 'sha256 second\n'})

    def test_newline_in_object_request_cannot_inject_a_second_command(self):
        ref = self.commit_files({'file.txt': 'regular content\n'})
        before = support.git(self.root, 'status', '--porcelain=v1')
        with journal.object_cache():
            with self.assertRaisesRegex(TaskError, 'TASK_PATH'):
                journal.blob(self.root, ref, 'file.txt\ncontents ' + ref + ':file.txt')
            self.assertEqual(journal.blob(self.root, ref, 'file.txt'), 'regular content\n')
        self.assertEqual(support.git(self.root, 'status', '--porcelain=v1'), before)

    def test_git_link_mode_cannot_be_accepted_as_a_regular_object(self):
        ref = self.commit_files({'file.txt': 'regular content\n'})
        oid = support.git(self.root, 'rev-parse', ref + ':file.txt')
        support.git(self.root, 'update-index', '--add', '--cacheinfo',
                    '120000,' + oid + ',file.txt')
        support.git(self.root, 'commit', '-qm', 'change mode to symlink')
        ref = support.git(self.root, 'rev-parse', 'HEAD')
        with journal.object_cache():
            with self.assertRaisesRegex(TaskError, 'TASK_PATH'):
                journal._committed_paths(self.root, ref, ['file.txt'])


if __name__ == '__main__':
    unittest.main()
