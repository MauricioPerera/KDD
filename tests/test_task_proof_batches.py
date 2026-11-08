"""Real Git proofs for same-stage identity/ancestry batches and safe fallback."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from tests import test_task_history_read_cost as graph
from tests import test_traceability_model as support
import task_git as journal
import validate_tasks as gate
from task_model import TaskError
from traceability_git import build_trace


def starts(path):
    return [record['argv'] for line in path.read_text(encoding='utf-8-sig').splitlines()
            if (record := json.loads(line)).get('event') == 'start']


def state(root):
    return (graph.git(root, 'rev-parse', 'HEAD'), graph.git(root, 'show-ref'),
            graph.git(root, 'status', '--porcelain=v1'),
            (root / '.git/index').read_bytes(), (root / '.git/config').read_bytes())


class TaskProofStages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_area = tempfile.TemporaryDirectory(prefix='kdd-proof-seeds-')
        cls.addClassCleanup(cls.seed_area.cleanup)
        cls.sources = {}
        for algorithm in ('sha1', 'sha256'):
            root = Path(cls.seed_area.name) / algorithm
            cls.sources[algorithm] = root, graph.initialize(root, algorithm)

    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-proof-case-')
        self.addCleanup(self.area.cleanup)
        self.owner = Path(self.area.name).resolve()
        self.sequence = 0

    def repository(self, algorithm='sha1', independent=False):
        self.sequence += 1
        source, refs = self.sources[algorithm]
        root = self.owner / ('repo-' + str(self.sequence))
        graph.git(self.owner, 'clone', '-q', '--no-hardlinks' if independent else '--shared',
                  str(source), str(root))
        graph.configure_git(root, {'user.name': 'Proof fixture',
                                   'user.email': 'proof@example.invalid'}, ephemeral=True)
        return root, dict(refs)

    def observe(self, operation):
        self.sequence += 1
        path = self.owner / ('events-' + str(self.sequence) + '.jsonl')
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(path)}):
            result = operation()
        self.assertTrue(path.is_file(), 'the proof must execute real Git')
        return result, starts(path)

    @staticmethod
    def proof(root, refs, **overrides):
        values = dict(base=refs['a'], tip=refs['b'], tested=refs['d'])
        values.update(overrides)
        return gate._proof_refs(root, dict(branch_base=values['base'], verified_ref=values['tested']),
                                dict(branch_tip=values['tip']))

    def test_approved_identity_and_ancestry_use_one_process_in_both_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm), journal.object_cache():
                root, refs = self.repository(algorithm)
                self.assertTrue(journal._native_oid(root, refs['b']))
                before = state(root)

                def prove():
                    journal._require_approved_ancestor(root, refs['b'], refs['d'])
                    return journal.commit_sha(root, refs['b'])

                result, commands = self.observe(prove)
                self.assertEqual(result, refs['b'])
                self.assertEqual(state(root), before)
                self.assertLessEqual(len(commands), 1, commands)

    def test_chain_and_its_typed_endpoints_use_one_process_in_both_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm), journal.object_cache():
                root, refs = self.repository(algorithm)
                self.assertTrue(journal._native_oid(root, refs['a']))
                before = state(root)

                def prove():
                    result = self.proof(root, refs)
                    journal._perimeter_refs(root, (refs['a'], refs['a'], refs['b'], refs['d']))
                    return result

                result, commands = self.observe(prove)
                self.assertEqual(result, [])
                self.assertEqual(state(root), before)
                self.assertLessEqual(len(commands), 1, commands)

    def test_divergent_first_edge_is_rejected_and_not_cached_after_replacement(self):
        root, refs = self.repository()
        replacement = graph.git(root, 'commit-tree', refs['tree'], '-p', refs['c'],
                                '-m', 'B now descends from the other side')
        with journal.object_cache():
            self.assertTrue(self.proof(root, refs, base=refs['c']))
            graph.git(root, 'replace', refs['b'], replacement)
            before = state(root)
            self.assertEqual(self.proof(root, refs, base=refs['c']), [])
            self.assertEqual(state(root), before)

    def test_noncanonical_chain_endpoints_are_not_certified_as_commits(self):
        for algorithm in ('sha1', 'sha256'):
            root, refs = self.repository(algorithm)
            graph.git(root, '-c', 'user.name=Proof', '-c', 'user.email=proof@example.invalid',
                      'tag', '-a', 'review', '-m', 'annotated identity', refs['b'])
            tag = graph.git(root, 'rev-parse', 'review')
            alias = 'e' * (64 if algorithm == 'sha1' else 40)
            graph.git(root, 'update-ref', 'refs/heads/' + alias, refs['b'])
            for tip in (tag, alias):
                with self.subTest(object_format=algorithm, endpoint=tip), journal.object_cache():
                    before = state(root)
                    self.assertEqual(self.proof(root, refs, tip=tip), [])
                    with self.assertRaisesRegex(TaskError, 'TASK_PERIMETER: canonical commit'):
                        journal._perimeter_refs(root, (refs['a'], tip, refs['d']))
                    self.assertEqual(state(root), before)

    def test_long_valid_chain_preserves_truth_when_the_auxiliary_window_is_partial(self):
        root, refs = self.repository()
        marks = self.owner / 'long-chain-marks'
        commands = []
        for number in range(1, 2056):
            commands.append('commit refs/heads/long\nmark :' + str(number) +
                            '\ncommitter Proof <proof@example.invalid> ' + str(1700000000 + number) +
                            ' +0000\ndata 0\n\n')
            if number > 1:
                commands.append('from :' + str(number - 1) + '\n')
            commands.append('deleteall\n\n')
        graph.git(root, 'fast-import', '--quiet', '--export-marks=' + str(marks), input=''.join(commands))
        values = dict(line.split() for line in marks.read_text(encoding='ascii').splitlines())
        refs.update(a=values[':1'], b=values[':2054'], d=values[':2055'])
        with journal.object_cache():
            self.assertTrue(journal._native_oid(root, refs['a']))
            before = state(root)
            result, observed = self.observe(lambda: self.proof(root, refs))
            self.assertEqual(result, [])
            self.assertEqual(state(root), before)
            self.assertLessEqual(len(observed), 3, observed)
            for command in observed:
                if 'rev-list' in command:
                    self.assertIn('--max-count=2048', command)

    def test_chain_rechecks_replacements_between_operations(self):
        root, refs = self.repository()
        with journal.object_cache():
            self.assertEqual(self.proof(root, refs), [])
        graph.git(root, 'replace', refs['d'], refs['c'])
        before = state(root)
        with journal.object_cache():
            self.assertTrue(self.proof(root, refs))
        self.assertEqual(state(root), before)

    def test_missing_endpoint_is_rejected_without_poisoning_recovery(self):
        root, refs = self.repository(independent=True)
        path = root / '.git/objects' / refs['d'][:2] / refs['d'][2:]
        self.assertTrue(path.resolve().is_relative_to(root.resolve()))
        self.assertEqual(path.stat().st_nlink, 1)
        original = path.read_bytes()
        path.chmod(stat.S_IREAD | stat.S_IWRITE)
        path.unlink()
        with journal.object_cache():
            self.assertTrue(self.proof(root, refs))
            path.write_bytes(original)
            self.assertEqual(self.proof(root, refs), [])

    def test_one_warm_edge_keeps_the_existing_single_query_path(self):
        root, refs = self.repository()
        with journal.object_cache():
            self.assertTrue(journal.ancestor(root, refs['a'], refs['b']))
            result, commands = self.observe(lambda: self.proof(root, refs))
            self.assertEqual(result, [])
            self.assertLessEqual(len(commands), 1, commands)


class ClosedTaskProofBudget(support.RepositoryFixture):
    def test_complete_snapshot_history_and_trace_use_at_most_48_git_processes(self):
        task = journal.read_tasks(self.root, self.refs['closed'])['TASK-001']
        before = state(self.root)
        trace = Path(self.temp.name) / 'closed-proof-events.jsonl'
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}), journal.object_cache():
            snapshot = gate.validate_snapshot(self.root, 'main')
            history = gate.validate_range(self.root, task['branch_base'], 'main')
            report = build_trace(self.root, 'main', 'quality/traceability.json', require_verified=True)
        self.assertEqual(snapshot, [])
        self.assertEqual(history, [])
        self.assertTrue(report['complete'], report)
        link = report['requirements'][0]['links'][0]
        self.assertEqual((link['approved_ref'], link['branch_tip'], link['tested_commit']),
                         (self.refs['approved'], self.refs['tip'], self.refs['tested']))
        receipt = json.loads((self.root / link['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(receipt['passed_tests'], 2)
        self.assertEqual(state(self.root), before)
        commands = starts(trace)
        self.assertLessEqual(len(commands), 48, 'real Git starts: ' + str(len(commands)))


if __name__ == '__main__':
    unittest.main()
