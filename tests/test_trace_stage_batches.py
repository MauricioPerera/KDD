"""New Git process budgets and atomic publication at existing trace stages."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import task_git as journal
from traceability_git import _Projection
from tests import test_trace_projection_fresh_read as fixture

CONTRACT = 'regular.txt'
ORACLE = 'empty.txt'
TARGET = 'literal \u00f1 name.txt'
NAMES = (CONTRACT, ORACLE, TARGET)
METADATA = dict(tests=ORACLE, target=TARGET)


class TraceStageBatches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.TraceProjectionFreshRead.setUpClass()
        cls.addClassCleanup(fixture.TraceProjectionFreshRead.doClassCleanups)

    def setUp(self):
        self.case = fixture.TraceProjectionFreshRead()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root, self.ref = self.case.root, fixture.TraceProjectionFreshRead.ref
        self.sequence = 0

    def repository(self, algorithm):
        if algorithm == 'sha1':
            return self.root, self.ref
        root = self.case.area_path / algorithm
        return root, fixture.TraceProjectionFreshRead.prepare(root, algorithm)

    def git(self, root, *args):
        return fixture.TraceProjectionFreshRead.git(root, *args).decode('utf-8').strip()

    def traced(self, call):
        self.sequence += 1
        trace = self.case.area_path / ('stage-' + str(self.sequence) + '.jsonl')
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
            result = call()
        starts = [row['argv'] for line in trace.read_text(encoding='utf-8-sig').splitlines()
                  if (row := json.loads(line)).get('event') == 'start']
        self.assertTrue(starts, 'the cold stage must execute real Git')
        return result, starts

    def unchanged(self, root):
        return (self.git(root, 'rev-parse', 'HEAD'), self.git(root, 'show-ref'),
                (root / '.git/index').read_bytes(), (root / '.git/config').read_bytes())

    def observed(self, root, invalid=False):
        path = root / (TARGET if invalid else 'later.txt')
        path.write_bytes(b'\xffinvalid utf8\n' if invalid else b'later independent work\n')
        self.git(root, 'add', path.name)
        self.git(root, 'commit', '-qm', 'Synthetic observed stage')
        return self.git(root, 'rev-parse', 'HEAD')

    def projection(self, root, tested, observed):
        projection = _Projection(root, observed, 'unused.json')
        for name in NAMES:
            projection.blob(tested, name)
        return projection, dict(contract=CONTRACT, verified_ref=tested)

    def test_contract_pair_uses_at_most_two_real_git_processes_in_both_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm), journal.object_cache():
                root, revision = self.repository(algorithm)
                projection = _Projection(root, revision, 'unused.json')
                self.assertTrue(journal._native_oid(root, revision))
                before = self.unchanged(root)
                values, starts = self.traced(lambda: projection._contract_inputs(revision, ORACLE, TARGET))
                self.assertEqual(values, ('', 'caf\u00e9\n'))
                self.assertEqual(sum('ls-tree' in argv for argv in starts), 1)
                self.assertLessEqual(len(starts), 2, starts)
                self.assertEqual(self.unchanged(root), before)

    def test_freshness_uses_at_most_one_real_git_process_in_both_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm), journal.object_cache():
                root, tested = self.repository(algorithm)
                observed = self.observed(root)
                projection, task = self.projection(root, tested, observed)
                self.assertTrue(journal._native_oid(root, observed))
                before = self.unchanged(root)
                result, starts = self.traced(lambda: projection._fresh(task, METADATA))
                self.assertTrue(result)
                self.assertLessEqual(len(starts), 1, starts)
                self.assertEqual(self.unchanged(root), before)

    def test_invalid_utf8_in_last_blob_does_not_publish_part_of_the_stage(self):
        observed = self.observed(self.root, invalid=True)
        projection, task = self.projection(self.root, self.ref, observed)
        before, git_before = dict(projection.objects), self.unchanged(self.root)
        self.assertFalse(projection._fresh(task, METADATA))
        self.assertEqual(projection.objects, before, 'an invalid stage must not publish a valid prefix')
        self.assertEqual(self.unchanged(self.root), git_before)


if __name__ == '__main__':
    unittest.main()