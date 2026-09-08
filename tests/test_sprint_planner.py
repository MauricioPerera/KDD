"""Acceptance oracle for backlog planning; authored before implementation."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.sprint_planner import plan_sprint


def task(identifier, **changes):
    value = {'id': identifier, 'status': 'ready', 'priority': 'medium',
             'dependencies': [], 'estimated_cost': 10}
    value.update(changes)
    return value


def snapshot(*tasks):
    return {'sprint': {'status': 'active', 'selected_tasks': [t['id'] for t in tasks],
                       'budget': {'unit': 'tokens', 'limit': 100, 'consumed': 0,
                                  'verification_reserve': 20}},
            'tasks': list(tasks)}


def blocker(identifier='credential'):
    return {'id': identifier, 'reason': 'Missing credentials', 'owner': 'operator',
            'condition': 'Credentials supplied', 'status': 'open'}


def evidence(valid=True):
    return {'valid': valid, 'reference': 'report@revision'}


def row(result, identifier):
    return next(item for item in result['tasks'] if item['id'] == identifier)


class PlannerTests(unittest.TestCase):
    def test_priority_and_stable_ties(self):
        data = snapshot(task('B'), task('Z', priority='urgent'), task('A'))
        result = plan_sprint(data)
        self.assertTrue(result['valid'])
        self.assertEqual(result['executable'], ['Z', 'A', 'B'])
        self.assertEqual(result['next_task'], 'Z')
        self.assertEqual([r['id'] for r in result['tasks']], ['A', 'B', 'Z'])

    def test_inheritance_and_explanation(self):
        data = snapshot(task('A', priority='low'), task('B', dependencies=['A']),
                        task('C', priority='urgent', dependencies=['B']),
                        task('D', priority='high'))
        result = plan_sprint(data)
        self.assertEqual(result['executable'], ['A', 'D'])
        self.assertEqual(row(result, 'A')['priority'], 'low')
        self.assertEqual(row(result, 'A')['effective_priority'], 'urgent')
        self.assertEqual(row(result, 'A')['priority_sources'], ['C'])
        self.assertEqual(row(result, 'A')['unlocks'], ['B', 'C'])
        self.assertEqual(row(result, 'C')['blocked_by'], ['B'])
        self.assertEqual(row(result, 'C')['root_causes'],
                         [{'task_id': 'A', 'code': 'DEPENDENCY_PENDING'}])

    def test_more_unlocks_break_priority_tie(self):
        data = snapshot(task('A'), task('Z'), task('B', dependencies=['Z']))
        self.assertEqual(plan_sprint(data)['executable'], ['Z', 'A'])

    def test_priority_cannot_admit_unselected_prerequisite(self):
        data = snapshot(task('A', priority='low'), task('B', priority='urgent', dependencies=['A']))
        data['sprint']['selected_tasks'] = ['B']
        result = plan_sprint(data)
        self.assertEqual(result['executable'], [])
        self.assertEqual(row(result, 'A')['effective_priority'], 'urgent')
        self.assertIn('TASK_NOT_SELECTED', row(result, 'A')['reasons'])
        self.assertIn({'task_id': 'A', 'code': 'TASK_NOT_SELECTED'}, row(result, 'B')['root_causes'])

    def test_no_inheritance_from_outside_or_cancelled_or_satisfied(self):
        for status, selected in [('ready', False), ('cancelled', True)]:
            with self.subTest(status=status):
                data = snapshot(task('A', priority='low'),
                                task('B', priority='urgent', dependencies=['A'], status=status))
                if not selected:
                    data['sprint']['selected_tasks'] = ['A']
                self.assertEqual(row(plan_sprint(data), 'A')['effective_priority'], 'low')
        data = snapshot(task('A', status='done', evidence=evidence(), priority='low'),
                        task('B', status='done', evidence=evidence(), priority='urgent', dependencies=['A']))
        self.assertEqual(row(plan_sprint(data), 'A')['effective_priority'], 'low')

    def test_manual_blocker_propagates_and_resolves(self):
        data = snapshot(task('A', blockers=[blocker()]), task('B', dependencies=['A']),
                        task('C', dependencies=['B']), task('D'))
        result = plan_sprint(data)
        self.assertEqual(result['executable'], ['D'])
        causes = row(result, 'C')['root_causes']
        self.assertEqual(len(causes), 1)
        self.assertEqual(causes[0]['task_id'], 'A')
        self.assertEqual(causes[0]['code'], 'MANUAL_BLOCKER')
        self.assertEqual(causes[0]['blocker'], blocker())
        data['tasks'][0]['blockers'][0]['status'] = 'resolved'
        self.assertEqual(plan_sprint(data)['next_task'], 'A')
        data['tasks'][0].update(status='done', evidence=evidence())
        self.assertEqual(plan_sprint(data)['next_task'], 'B')

    def test_indirect_evidence_invalidation_and_reactivation(self):
        data = snapshot(task('A', status='done', evidence=evidence()),
                        task('B', status='done', evidence=evidence(), dependencies=['A']),
                        task('C', dependencies=['B']))
        result = plan_sprint(data)
        self.assertEqual(result['executable'], ['C'])
        self.assertEqual(row(result, 'C')['recheck_on'], ['A', 'B', 'C'])
        data['tasks'][0]['evidence']['valid'] = False
        result = plan_sprint(data)
        self.assertEqual(result['executable'], [])
        self.assertFalse(row(result, 'B')['satisfied'])
        self.assertIn({'task_id': 'A', 'code': 'EVIDENCE_INVALID'}, row(result, 'C')['root_causes'])
        data['tasks'][0]['evidence']['valid'] = True
        self.assertEqual(plan_sprint(data)['executable'], ['C'])

    def test_completed_ids_cannot_override_evidence(self):
        data = snapshot(task('A', status='done'), task('B', dependencies=['A']))
        data['sprint']['completed_tasks'] = ['A', 'B']
        self.assertEqual(plan_sprint(data)['executable'], [])

    def test_open_blocker_invalidates_done(self):
        data = snapshot(task('A', status='done', evidence=evidence(), blockers=[blocker()]),
                        task('B', dependencies=['A']))
        result = plan_sprint(data)
        self.assertFalse(row(result, 'A')['satisfied'])
        self.assertEqual(result['executable'], [])

    def test_cycles_and_independent_work(self):
        data = snapshot(task('A', dependencies=['B']), task('B', dependencies=['A']),
                        task('C', dependencies=['B']), task('D'))
        result = plan_sprint(data)
        self.assertTrue(result['valid'])
        self.assertEqual(result['cycles'], [['A', 'B']])
        self.assertEqual(result['executable'], ['D'])
        self.assertIn('DEPENDENCY_CYCLE', row(result, 'A')['reasons'])
        self.assertEqual({c['task_id'] for c in row(result, 'C')['root_causes']}, {'A', 'B'})

    def test_self_cycle_and_done_cycle(self):
        self.assertEqual(plan_sprint(snapshot(task('A', dependencies=['A'])))['cycles'], [['A']])
        data = snapshot(task('A', status='done', evidence=evidence(), dependencies=['B']),
                        task('B', status='done', evidence=evidence(), dependencies=['A']))
        self.assertFalse(any(r['satisfied'] for r in plan_sprint(data)['tasks']))

    def test_distinct_cycles(self):
        data = snapshot(task('A', dependencies=['B']), task('B', dependencies=['A']),
                        task('C', dependencies=['D']), task('D', dependencies=['C']))
        self.assertEqual(plan_sprint(data)['cycles'], [['A', 'B'], ['C', 'D']])

    def test_relations_are_informational(self):
        relations = [{'type': 'related_to', 'target': 'B'}, {'type': 'duplicates', 'target': 'B'},
                     {'type': 'goal', 'target': 'checkout'}, {'type': 'contract', 'target': 'specs/C.md'}]
        data = snapshot(task('A', relations=relations),
                        task('B', blockers=[blocker()], relations=[{'type': 'related_to', 'target': 'A'}]))
        result = plan_sprint(data)
        self.assertEqual(result['executable'], ['A'])
        self.assertEqual(result['cycles'], [])
        self.assertCountEqual(row(result, 'A')['relations'], relations)

    def test_lifecycle_not_ready(self):
        for status in ['backlog', 'in_progress', 'cancelled', 'done']:
            with self.subTest(status=status):
                self.assertEqual(plan_sprint(snapshot(task('A', status=status)))['executable'], [])

    def test_sprint_inactive_and_budget_use_admission(self):
        data = snapshot(task('A', priority='urgent', estimated_cost=81), task('B'))
        result = plan_sprint(data)
        self.assertEqual(result['executable'], ['B'])
        self.assertIn('BUDGET_EXCEEDED', row(result, 'A')['reasons'])
        data['sprint']['status'] = 'paused'
        self.assertEqual(plan_sprint(data)['executable'], [])

    def test_verification_reserve_and_alternatives_not_batch(self):
        data = snapshot(task('A', estimated_cost=80), task('B', estimated_cost=80))
        self.assertEqual(plan_sprint(data)['executable'], ['A', 'B'])
        self.assertEqual(plan_sprint(data)['next_task'], 'A')
        data['sprint']['budget']['consumed'] = 80
        data['tasks'][0].update(estimated_cost=20, phase='verification')
        self.assertEqual(plan_sprint(data)['executable'], ['A'])

    def test_multiple_roots_deduplicated(self):
        data = snapshot(task('A', blockers=[blocker()]), task('B', dependencies=['A']),
                        task('C', dependencies=['A']), task('D', dependencies=['B', 'C']))
        self.assertEqual(len(row(plan_sprint(data), 'D')['root_causes']), 1)
        data['tasks'][2]['blockers'] = [blocker('second')]
        self.assertEqual(len(row(plan_sprint(data), 'D')['root_causes']), 2)

    def test_budget_root_explained_through_chain(self):
        data = snapshot(task('A', estimated_cost=81), task('B', dependencies=['A']))
        self.assertIn({'task_id': 'A', 'code': 'BUDGET_EXCEEDED'}, row(plan_sprint(data), 'B')['root_causes'])

    def test_invalid_snapshots(self):
        values = [None, [], {}, {'sprint': {}, 'tasks': []}]
        values += [snapshot(task('A'), task('A')),
                   snapshot(task('A', dependencies=['missing'])),
                   snapshot(task('A', dependencies=['A', 'A'])),
                   snapshot(task('A', priority='critical')),
                   snapshot(task('A', priority=[])),
                   snapshot(task('A', estimated_cost=True)),
                   snapshot(task('A', evidence={'valid': 'yes', 'reference': 'R'})),
                   snapshot(task('A', evidence={'valid': True, 'reference': ''})),
                   snapshot(task('A', relations=[{'type': 'related_to', 'target': 'missing'}])),
                   snapshot(task('A', blockers=[{'id': 'missing-fields'}])),
                   snapshot(task(' A '))]
        for data in values:
            with self.subTest(data=data):
                result = plan_sprint(data)
                self.assertFalse(result['valid'])
                self.assertEqual(result['executable'], [])
                self.assertIsNone(result['next_task'])
                self.assertTrue(result['errors'])

    def test_missing_required_fields_and_unknown_selection(self):
        for key in task('A'):
            data = snapshot(task('A'))
            del data['tasks'][0][key]
            self.assertFalse(plan_sprint(data)['valid'], key)
        data = snapshot(task('A'))
        data['sprint']['selected_tasks'] = ['missing']
        self.assertFalse(plan_sprint(data)['valid'])
        data = snapshot(task('A'))
        data['sprint']['budget']['consumed'] = None
        self.assertFalse(plan_sprint(data)['valid'])

    def test_empty_completed_and_nonmutation(self):
        self.assertEqual(plan_sprint(snapshot())['executable'], [])
        data = snapshot(task('A', status='done', evidence=evidence()))
        before = copy.deepcopy(data)
        result = plan_sprint(data)
        self.assertEqual(result['executable'], [])
        self.assertTrue(row(result, 'A')['satisfied'])
        result['tasks'][0]['relations'].append({'type': 'goal', 'target': 'mutated'})
        self.assertEqual(data, before)

    def test_determinism_under_input_permutation(self):
        data = snapshot(task('C', dependencies=['A', 'B']), task('A'), task('B'))
        before = copy.deepcopy(data)
        result = plan_sprint(data)
        self.assertEqual(data, before)
        data['tasks'].reverse()
        data['sprint']['selected_tasks'].reverse()
        data['tasks'][-1]['dependencies'].reverse()
        self.assertEqual(plan_sprint(data), result)

    def test_chain_beyond_recursion_limit(self):
        count = 1100
        tasks = [task(str(i), status='done', evidence=evidence(),
                      dependencies=[str(i - 1)] if i else []) for i in range(count)]
        tasks[-1]['status'] = 'ready'
        data = snapshot(*tasks)
        self.assertEqual(plan_sprint(data)['executable'], [str(count - 1)])

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backlog.json'
            cases = [(snapshot(task('A')), 0),
                     (snapshot(task('A', blockers=[blocker()])), 1), ({}, 2)]
            for value, code in cases:
                path.write_text(json.dumps(value), encoding='utf-8')
                process = subprocess.run([sys.executable, '-m', 'src.sprint_planner', str(path)],
                                         cwd=Path(__file__).resolve().parents[1],
                                         capture_output=True, text=True, timeout=15)
                self.assertEqual(process.returncode, code, process.stderr)
                self.assertEqual(json.loads(process.stdout), plan_sprint(value))
            path.write_text('{', encoding='utf-8')
            process = subprocess.run([sys.executable, '-m', 'src.sprint_planner', str(path)],
                                     cwd=Path(__file__).resolve().parents[1],
                                     capture_output=True, text=True, timeout=15)
            self.assertEqual(process.returncode, 2)
            self.assertFalse(json.loads(process.stdout)['valid'])


if __name__ == '__main__':
    unittest.main()
