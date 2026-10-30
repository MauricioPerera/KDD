"""Changes to the quality gate must satisfy its existing complexity budget."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_budgets import validate_directory


class QualityBudgetReview(unittest.TestCase):
    def test_quality_gate_respects_its_declared_budget(self):
        self.assertEqual(validate_directory(str(ROOT / 'knowledge/contracts'), str(ROOT),
                                             'verify-quality'), [])

    def test_changed_profiles_and_command_gate_respect_their_budgets(self):
        for task in ('run-profile', 'test-command-gate'):
            with self.subTest(task=task):
                self.assertEqual(validate_directory(str(ROOT / 'knowledge/contracts'),
                                                     str(ROOT), task), [])
