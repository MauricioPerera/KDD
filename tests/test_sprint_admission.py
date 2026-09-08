"""Frozen acceptance oracle for the admission pilot, including the public CLI."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.sprint_admission import validate_admission


def fixture():
    return {
        'sprint': {
            'status': 'active', 'selected_tasks': ['A'], 'completed_tasks': ['D'],
            'budget': {'unit': 'tokens', 'limit': 100, 'consumed': 60,
                       'verification_reserve': 20},
        },
        'request': {'task_id': 'A', 'dependencies': ['D'],
                    'estimated_cost': 20, 'phase': 'implementation'},
    }


class AdmissionTests(unittest.TestCase):
    def check(self, data, reason=None):
        result = validate_admission(data)
        self.assertEqual(result['admitted'], reason is None)
        if reason is None:
            self.assertEqual(result['reasons'], [])
        else:
            self.assertIn(reason, result['reasons'])

    def test_boundary_and_no_mutation(self):
        data = fixture()
        before = copy.deepcopy(data)
        self.check(data)
        self.assertEqual(data, before)
        self.assertEqual(validate_admission(data), validate_admission(data))

    def test_inactive(self):
        for status in ['draft', 'paused', 'closed', 'cancelled']:
            with self.subTest(status=status):
                data = fixture()
                data['sprint']['status'] = status
                self.check(data, 'SPRINT_NOT_ACTIVE')

    def test_not_selected(self):
        data = fixture()
        data['request']['task_id'] = 'B'
        self.check(data, 'TASK_NOT_SELECTED')

    def test_dependencies(self):
        data = fixture()
        data['sprint']['completed_tasks'] = []
        self.check(data, 'DEPENDENCIES_PENDING')
        data['request']['dependencies'] = []
        self.check(data)

    def test_budget_over_boundary(self):
        data = fixture()
        data['request']['estimated_cost'] = 21
        self.check(data, 'BUDGET_EXCEEDED')
        data['sprint']['budget']['consumed'] = 101
        data['request']['estimated_cost'] = 0
        self.check(data, 'BUDGET_EXCEEDED')

    def test_verification_spends_reserve(self):
        data = fixture()
        data['sprint']['budget']['consumed'] = 80
        self.check(data, 'BUDGET_EXCEEDED')
        data['request']['phase'] = 'verification'
        self.check(data)
        data['request']['estimated_cost'] = 10
        self.check(data)  # 80 + 10 + remaining reserve 10 = 100
        data['request']['estimated_cost'] = 21
        self.check(data, 'BUDGET_EXCEEDED')

    def test_accumulates_business_rejections(self):
        data = fixture()
        data['sprint']['status'] = 'paused'
        data['sprint']['selected_tasks'] = []
        data['sprint']['completed_tasks'] = []
        data['request']['estimated_cost'] = 99
        self.assertEqual(validate_admission(data), {
            'admitted': False, 'reasons': ['SPRINT_NOT_ACTIVE', 'TASK_NOT_SELECTED',
                                         'DEPENDENCIES_PENDING', 'BUDGET_EXCEEDED']})

    def test_invalid_numbers_fail_closed(self):
        for key in ['limit', 'consumed', 'verification_reserve']:
            for value in [-1, True, None, '20', 1.5, float('inf'), float('nan')]:
                with self.subTest(key=key, value=value):
                    data = fixture()
                    data['sprint']['budget'][key] = value
                    self.check(data, 'INVALID_INPUT')
        for value in [-1, False, None, '1', 0.5]:
            data = fixture()
            data['request']['estimated_cost'] = value
            self.check(data, 'INVALID_INPUT')

    def test_missing_fields(self):
        for parent in ['sprint', 'request']:
            for key in fixture()[parent]:
                data = fixture()
                del data[parent][key]
                self.check(data, 'INVALID_INPUT')
        for key in fixture()['sprint']['budget']:
            data = fixture()
            del data['sprint']['budget'][key]
            self.check(data, 'INVALID_INPUT')

    def test_invalid_shapes(self):
        for data in [None, [], 42, {}, {'sprint': [], 'request': None}]:
            self.check(data, 'INVALID_INPUT')
        mutations = [
            ('sprint', 'status', 'activ'),
            ('sprint', 'selected_tasks', ['A', 'A']),
            ('sprint', 'completed_tasks', ['']),
            ('request', 'dependencies', 'D'),
            ('request', 'dependencies', ['A']),
            ('request', 'task_id', ''),
            ('request', 'phase', 'other'),
        ]
        for parent, key, value in mutations:
            data = fixture()
            data[parent][key] = value
            self.check(data, 'INVALID_INPUT')
        data = fixture()
        data['sprint']['budget']['unit'] = ''
        self.check(data, 'INVALID_INPUT')
        data = fixture()
        data['sprint']['budget']['verification_reserve'] = 101
        self.check(data, 'INVALID_INPUT')

    def test_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for mode, expected_code, reason in [
                ('valid', 0, None), ('rejected', 1, 'TASK_NOT_SELECTED'),
                ('malformed', 2, 'INVALID_INPUT'), ('missing', 2, 'INVALID_INPUT'),
            ]:
                with self.subTest(mode=mode):
                    data = fixture()
                    if mode == 'rejected':
                        data['request']['task_id'] = 'B'
                    path.write_text('{' if mode == 'malformed' else json.dumps(data),
                                    encoding='utf-8')
                    target = path if mode != 'missing' else path.with_name('absent.json')
                    result = subprocess.run(
                        [sys.executable, '-m', 'src.sprint_admission', str(target)],
                        cwd=Path(__file__).resolve().parents[1],
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, expected_code, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(report['admitted'], expected_code == 0)
                    if reason:
                        self.assertIn(reason, report['reasons'])


if __name__ == '__main__':
    unittest.main()
