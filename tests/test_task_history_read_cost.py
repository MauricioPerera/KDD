"""Real Git/Trace2 oracle for bounded task-history reads and unchanged rejection."""
import hashlib
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
import validate_tasks as gate
from tests.test_task_git import Repository


def git(root, *args, input=None):
    data = input.encode('utf-8') if input is not None else None
    return subprocess.run(['git', '-C', str(root), *args], input=data,
        capture_output=True, check=True, timeout=30).stdout.decode('utf-8').strip()


def initialize(root, algorithm='sha1'):
    root.mkdir()
    git(root, 'init', '-q', '-b', 'main', '--object-format=' + algorithm)
    for key, value in [('user.name', 'KDD Graph Test'), ('user.email', 'graph@example.test'),
                       ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
        git(root, 'config', key, value)
    tree = git(root, 'mktree', input='')
    a = git(root, 'commit-tree', tree, '-m', 'root A')
    b = git(root, 'commit-tree', tree, '-p', a, '-m', 'left B')
    c = git(root, 'commit-tree', tree, '-p', a, '-m', 'right C')
    d = git(root, 'commit-tree', tree, '-p', b, '-p', c, '-m', 'merge D')
    e = git(root, 'commit-tree', tree, '-m', 'unrelated E')
    git(root, 'update-ref', 'refs/heads/main', d)
    return dict(a=a, b=b, c=c, d=d, e=e, tree=tree)


class TraceCase(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-graph-read-')
        self.addCleanup(self.area.cleanup)
        self.area_path = Path(self.area.name).resolve()
        self.trace_number = 0

    def clone(self, source, name='repo-\u00f1'):
        target = self.area_path / name
        git(self.area_path, 'clone', '-q', '--shared', '--branch', 'main', str(source), str(target))
        return target

    def observe(self, operation):
        self.trace_number += 1
        trace = self.area_path / ('trace-' + str(self.trace_number) + '.jsonl')
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
            result = operation()
        self.assertTrue(trace.is_file(), 'real Git must produce Trace2 events')
        events = [json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()]
        commands = [event['argv'] for event in events if event.get('event') == 'start']
        self.assertTrue(commands)
        return result, commands

    @staticmethod
    def ancestor_commands(commands):
        return [argv for argv in commands if 'merge-base' in argv and '--is-ancestor' in argv]


class AncestryReadCost(TraceCase):
    @classmethod
    def setUpClass(cls):
        cls.source_area = tempfile.TemporaryDirectory(prefix='kdd-shared-graph-')
        cls.source = Path(cls.source_area.name) / 'source'
        cls.refs = initialize(cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.source_area.cleanup()

    def setUp(self):
        super().setUp()
        self.root = self.clone(self.source)

    def repeated(self, before, after, count=20):
        with journal.object_cache():
            return [journal.ancestor(self.root, before, after) for _ in range(count)]

    def test_positive_sha_pair_is_proved_once_per_operation(self):
        values, commands = self.observe(lambda: self.repeated(self.refs['b'], self.refs['d']))
        self.assertEqual(values, [True] * 20)
        self.assertEqual(len(self.ancestor_commands(commands)), 1)

    def test_negative_results_always_reach_git(self):
        values, commands = self.observe(lambda: self.repeated(self.refs['b'], self.refs['c'], 3))
        self.assertEqual(values, [False] * 3)
        self.assertEqual(len(self.ancestor_commands(commands)), 3)

    def test_missing_object_is_rechecked_after_being_written(self):
        content = ('tree ' + self.refs['tree'] + '\nparent ' + self.refs['d'] +
            '\nauthor KDD <graph@example.test> 1700000000 +0000\n'
            'committer KDD <graph@example.test> 1700000000 +0000\n\nnew object\n')
        future = git(self.root, 'hash-object', '-t', 'commit', '--stdin', input=content)
        def run():
            with journal.object_cache():
                before = journal.ancestor(self.root, self.refs['d'], future)
                written = git(self.root, 'hash-object', '-w', '-t', 'commit', '--stdin', input=content)
                self.assertEqual(written, future)
                return before, journal.ancestor(self.root, self.refs['d'], future)
        values, commands = self.observe(run)
        self.assertEqual(values, (False, True))
        self.assertEqual(len(self.ancestor_commands(commands)), 2)

    def test_symbolic_ref_is_fresh_even_inside_an_operation(self):
        def run():
            with journal.object_cache():
                first = journal.ancestor(self.root, self.refs['b'], 'main')
                git(self.root, 'update-ref', 'refs/heads/main', self.refs['c'])
                return first, journal.ancestor(self.root, self.refs['b'], 'main')
        values, commands = self.observe(run)
        self.assertEqual(values, (True, False))
        self.assertEqual(len(self.ancestor_commands(commands)), 2)

    def test_nested_contexts_share_only_the_outer_operation(self):
        def run():
            with journal.object_cache():
                self.assertTrue(journal.ancestor(self.root, self.refs['b'], self.refs['d']))
                with journal.object_cache():
                    self.assertTrue(journal.ancestor(self.root, self.refs['b'], self.refs['d']))
            with journal.object_cache():
                return journal.ancestor(self.root, self.refs['b'], self.refs['d'])
        result, commands = self.observe(run)
        self.assertTrue(result)
        self.assertEqual(len(self.ancestor_commands(commands)), 2)

    def test_exception_discards_the_operation_cache(self):
        def run():
            with self.assertRaisesRegex(RuntimeError, 'stop operation'):
                with journal.object_cache():
                    self.assertTrue(journal.ancestor(self.root, self.refs['b'], self.refs['d']))
                    raise RuntimeError('stop operation')
            return self.repeated(self.refs['b'], self.refs['d'], 2)
        values, commands = self.observe(run)
        self.assertEqual(values, [True, True])
        self.assertEqual(len(self.ancestor_commands(commands)), 2)

    def test_without_context_each_query_is_fresh(self):
        values, commands = self.observe(lambda: [journal.ancestor(
            self.root, self.refs['b'], self.refs['d']) for _ in range(3)])
        self.assertEqual(values, [True] * 3)
        self.assertEqual(len(self.ancestor_commands(commands)), 3)

    def test_replace_ref_is_reread_between_operations(self):
        self.assertEqual(self.repeated(self.refs['b'], self.refs['d'], 2), [True, True])
        git(self.root, 'replace', self.refs['d'], self.refs['c'])
        self.assertEqual(self.repeated(self.refs['b'], self.refs['d'], 2), [False, False])
        git(self.root, 'replace', '-d', self.refs['d'])
        self.assertEqual(self.repeated(self.refs['b'], self.refs['d'], 2), [True, True])

    def test_repository_identity_prevents_cross_repository_proofs(self):
        other = self.clone(self.source, 'other')
        git(other, 'replace', self.refs['d'], self.refs['c'])
        def run():
            with journal.object_cache():
                return (journal.ancestor(self.root, self.refs['b'], self.refs['d']),
                        journal.ancestor(other, self.refs['b'], self.refs['d']),
                        journal.ancestor(self.root, self.refs['b'], self.refs['d']))
        values, commands = self.observe(run)
        self.assertEqual(values, (True, False, True))
        self.assertEqual(len(self.ancestor_commands(commands)), 2)

    def test_merge_relations_and_unrelated_roots_keep_git_semantics(self):
        pairs = [('a', 'd', True), ('b', 'd', True), ('c', 'd', True),
                 ('d', 'b', False), ('b', 'c', False), ('e', 'd', False)]
        with journal.object_cache():
            for before, after, expected in pairs:
                with self.subTest(before=before, after=after):
                    self.assertIs(journal.ancestor(self.root, self.refs[before], self.refs[after]), expected)

    def test_equal_commit_is_also_proved_once(self):
        values, commands = self.observe(lambda: self.repeated(self.refs['d'], self.refs['d'], 3))
        self.assertEqual(values, [True] * 3)
        self.assertEqual(len(self.ancestor_commands(commands)), 1)

    def test_sha256_repository_uses_full_object_ids(self):
        root = self.area_path / 'sha256'
        refs = initialize(root, 'sha256')
        self.assertEqual(len(refs['d']), 64)
        def run():
            with journal.object_cache():
                return [journal.ancestor(root, refs['b'], refs['d']) for _ in range(2)]
        values, commands = self.observe(run)
        self.assertEqual(values, [True, True])
        self.assertEqual(len(self.ancestor_commands(commands)), 1)


class HistoryReadCost(TraceCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Repository()
        try:
            cls.repo.start()
            cls.repo.act('block', reason='review input')
            cls.repo.act('resume', reason='input approved')
            cls.repo.act('start', assignee='developer')
            cls.repo.integrate()
            cls.closed = cls.repo.act('finish')['task']
            cls.entries = journal.history(cls.repo.root, 'TASK-001')
            cls.repo.git('branch', 'delivery', 'main')
            cls.repo.git('switch', '-q', '--detach', cls.repo.approved)
            cls.repo.git('branch', '-f', 'main', cls.repo.approved)
            cls.repo.git('switch', '-q', 'main')
            cls.repo.git('merge', '--no-ff', '-qm', 'publish original journal', 'delivery')
            trace = Path(cls.repo.temp.name).parent / (Path(cls.repo.temp.name).name + '-history-trace.jsonl')
            try:
                with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
                    cls.findings = gate.validate_range(cls.repo.root, cls.repo.approved, 'main')
                cls.commands = [json.loads(line)['argv'] for line in
                    trace.read_text(encoding='utf-8-sig').splitlines()
                    if json.loads(line).get('event') == 'start']
            finally:
                trace.unlink(missing_ok=True)
        except BaseException:
            cls.repo.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.repo.close()

    def project(self):
        root = self.clone(self.repo.root)
        for key, value in [('user.name', 'KDD History Test'), ('user.email', 'history@example.test'),
                           ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
            git(root, 'config', key, value)
        return root

    def commit(self, root, message):
        git(root, 'add', '-A')
        git(root, 'commit', '-qm', message)
        return git(root, 'rev-parse', 'HEAD')

    def test_valid_import_reads_parent_rows_without_individual_queries(self):
        self.assertEqual(self.findings, [])
        queries = [argv for argv in self.commands if 'rev-list' in argv and '--parents' in argv]
        self.assertTrue(queries)
        self.assertTrue(all('--first-parent' in argv and '--reverse' in argv for argv in queries))
        self.assertFalse(any('-n' in argv for argv in queries))

    def test_one_positive_proof_per_sha_pair_in_complete_audit(self):
        self.assertEqual(self.findings, [])
        pairs = [tuple(argv[-2:]) for argv in self.ancestor_commands(self.commands)]
        self.assertTrue(pairs)
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(journal.history(self.repo.root, 'TASK-001'), self.entries)
        self.assertEqual(journal.read_tasks(self.repo.root)['TASK-001'], self.closed)

    def test_deletion_restored_at_tip_still_reports_its_commit(self):
        root = self.project()
        path = root / 'knowledge/tasks/TASK-001.md'
        original = path.read_bytes()
        path.unlink()
        bad = self.commit(root, 'delete intermediate node')
        path.write_bytes(original)
        self.commit(root, 'restore identical final node')
        self.assertEqual(gate.validate_snapshot(root, 'main'), [])
        findings = gate.validate_range(root, self.repo.approved, 'main')
        self.assertTrue(any(bad in finding and 'TASK_DELETE' in finding for finding in findings))

    def test_unrelated_change_in_transition_remains_rejected_after_restoration(self):
        root = self.project()
        path = root / 'knowledge/tasks/TASK-002.md'
        task = journal.new_task('TASK-002', 'Second', 'Real node', self.repo.contract)
        path.write_text(journal.render_task(task), encoding='utf-8')
        (root / 'src/value.py').write_text('def value():\n return 7 # unrelated\n', encoding='utf-8')
        bad = self.commit(root, 'create task mixed with product change')
        git(root, 'checkout', self.repo.approved, '--', 'src/value.py')
        self.commit(root, 'restore product without undoing task')
        self.assertEqual(gate.validate_snapshot(root, 'main'), [])
        findings = gate.validate_range(root, self.repo.approved, 'main')
        self.assertTrue(any(bad in finding and 'TASK_SCOPE' in finding for finding in findings))

    def test_evidence_tampering_is_rejected_after_valid_operation(self):
        root = self.project()
        self.assertEqual(gate.validate_snapshot(root, 'main'), [])
        evidence = root / self.closed['evidence']
        evidence.write_text('{}\n', encoding='utf-8')
        self.commit(root, 'tamper committed evidence')
        findings = gate.validate_snapshot(root, 'main')
        self.assertTrue(any('TASK_EVIDENCE' in finding for finding in findings))

    def test_second_parent_base_is_not_treated_as_first_parent(self):
        source_tip = git(self.repo.root, 'rev-parse', 'refs/heads/delivery')
        findings = gate.validate_range(self.repo.root, source_tip, 'main')
        self.assertTrue(any('TASK_BASELINE' in finding for finding in findings))

    def test_moving_main_between_range_calls_does_not_reuse_previous_pass(self):
        root = self.project()
        self.assertEqual(gate.validate_range(root, self.repo.approved, 'main'), [])
        (root / 'knowledge/tasks/TASK-001.md').unlink()
        bad = self.commit(root, 'delete task after a successful audit')
        findings = gate.validate_range(root, self.repo.approved, 'main')
        self.assertTrue(any(bad in finding and 'TASK_DELETE' in finding for finding in findings))

    def test_validation_does_not_write_checkout_index_or_refs(self):
        root = self.project()
        canary = root / 'untracked-canary'
        canary.write_bytes(b'preserve\x00\xff')
        (root / 'src/value.py').write_text('raise RuntimeError("must not execute")\n', encoding='utf-8')
        git(root, 'add', 'src/value.py')
        def state():
            status = git(root, 'status', '--porcelain=v1', '--untracked-files=all')
            return (status, git(root, 'rev-parse', 'HEAD'),
                git(root, 'for-each-ref', '--format=%(refname) %(objectname)'),
                hashlib.sha256((root / '.git/index').read_bytes()).hexdigest(),
                (root / 'src/value.py').read_bytes(), canary.read_bytes())
        before = state()
        self.assertEqual(gate.validate_range(root, self.repo.approved, 'main'), [])
        self.assertEqual(state(), before)


if __name__ == '__main__':
    unittest.main()
