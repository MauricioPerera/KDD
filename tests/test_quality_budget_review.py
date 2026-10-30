"""Changed gates must add no budget debt against the incoming reviewed main."""
from pathlib import Path
import sys
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_budgets import validate_directory


class QualityBudgetReview(unittest.TestCase):
    def assert_no_new_budget_findings(self, task):
        baseline = json.loads((ROOT / 'tests/fixtures/methodology-budget-baseline.json').read_text())
        def metrics(finding):
            prefix, measured, limit = re.fullmatch(r'(.*?)=(\d+) excede .*?=(\d+)', finding).groups()
            return prefix, int(measured), int(limit)
        inherited = {key: (value, limit) for key, value, limit in map(metrics, baseline['findings'])}
        current = [str(item) for item in validate_directory(str(ROOT / 'knowledge/contracts'), str(ROOT), task)]
        for finding in current:
            key, measured, limit = metrics(finding)
            self.assertIn(key, inherited, finding)
            self.assertLessEqual(measured, inherited[key][0], finding)
            self.assertEqual(limit, inherited[key][1], finding)

    def test_quality_gate_respects_its_declared_budget(self):
        self.assert_no_new_budget_findings('verify-quality')

    def test_changed_profiles_and_command_gate_respect_their_budgets(self):
        for task in ('run-profile', 'test-command-gate'):
            with self.subTest(task=task):
                self.assert_no_new_budget_findings(task)
