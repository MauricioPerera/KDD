"""Real Git replacements must not turn stale projection data into evidence."""
from unittest.mock import patch

from tests import test_traceability_model as support
import task_git as journal
import traceability_git as trace


class ReplacementDuringProjection(support.RepositoryFixture):
    def replacement(self, mode):
        old = self.refs['closed']
        path = 'knowledge/tasks/TASK-001.md' if mode == 'task' else 'src/value.py'
        if mode == 'history':
            tree = support.git(self.root, 'rev-parse', old + '^{tree}')
            parents = []
        else:
            oid = support.git(self.root, 'rev-parse', old + ':' + path)
            parents = support.git(self.root, 'show', '-s', '--format=%P', old).split()
            support.git(self.root, 'update-index', '--cacheinfo', '120000,' + oid + ',' + path)
            tree = support.git(self.root, 'write-tree')
            support.git(self.root, 'reset', '--hard', old)
        args = ['commit-tree', tree]
        for parent in parents:
            args += ['-p', parent]
        new = support.git(self.root, *args, '-m', 'synthetic Git replacement')
        return old, new, path

    def projected(self, mode):
        old, new, path = self.replacement(mode)
        evidence = journal.read_tasks(self.root, old)['TASK-001']['evidence']
        observed = []

        def replace():
            if observed:
                return
            support.git(self.root, 'replace', old, new)
            if mode == 'history':
                self.assertEqual(support.git(self.root, 'show', '-s', '--format=%P', old), '')
            else:
                self.assertTrue(support.git(self.root, 'ls-tree', old, '--', path).startswith('120000'))
            observed.append(True)

        if mode == 'task':
            original = trace.parse_plan
            def hook(*args, **kwargs):
                result = original(*args, **kwargs)
                replace()
                return result
            target, name = trace, 'parse_plan'
        elif mode == 'target':
            original = trace._Projection.blob
            def hook(projection, revision, name):
                result = original(projection, revision, name)
                if name == evidence:
                    replace()
                return result
            target, name = trace._Projection, 'blob'
        else:
            original = trace._Projection._audit_index
            def hook(projection, *args):
                result = original(projection, *args)
                replace()
                return result
            target, name = trace._Projection, '_audit_index'
        with patch.object(target, name, hook):
            report = trace.build_trace(self.root, 'main', 'quality/traceability.json',
                                       require_verified=True)
        self.assertEqual(observed, [True], 'the real replacement must occur during projection')
        self.assertFalse(report['complete'], report)
        self.assertFalse(report['ok'], report)
        return {finding['code'] for finding in report['findings']}

    def test_task_node_replaced_by_symlink_is_not_verified(self):
        self.assertIn('TRACE_INPUT', self.projected('task'))

    def test_product_replaced_by_symlink_is_not_verified(self):
        self.assertIn('TRACE_STALE', self.projected('target'))

    def test_replaced_history_is_audited_after_the_change(self):
        self.assertIn('TRACE_JOURNAL', self.projected('history'))
