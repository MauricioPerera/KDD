"""Integration checks for rule-engine behavior and its declared budget."""

import copy
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rule_engine import evaluate


class RuleEngineComplexityIntegration(unittest.TestCase):
    def test_combined_families_and_stable_violation_order(self):
        rules = {
            "required": [{"field": "name"}],
            "type": [{"field": "amount", "kind": "number"}],
            "bounds": [{"field": "amount", "min": 1}],
            "refs": [{"field": "country", "collection": "countries"}],
            "keyed_bounds": [{"field": "amount", "key": "country", "table": "limits", "max_path": "max"}],
            "keyed_enums": [{"field": "currency", "key": "country", "table": "limits", "values_path": "currencies"}],
            "each": [{"collection": "items", "rules": {"required": [{"field": "sku"}]}}],
        }
        record = {"name": "", "amount": 11, "country": "AR", "currency": "EUR", "items": [{}, 7]}
        refs = {"countries": {"AR": {}}, "limits": {"AR": {"max": 10, "currencies": ["USD"]}}}
        original = copy.deepcopy((rules, record, refs))
        expected = ["amount: keyed bounds violated", "currency: keyed enum not allowed",
                    "items: elemento 0: sku: required", "items: element at index 1 is not a dict", "name: required"]
        self.assertEqual(evaluate(rules, record, refs), expected)
        self.assertEqual(evaluate(rules, record, refs), expected)
        self.assertEqual((rules, record, refs), original)

    def test_nonfinite_and_malformed_keyed_references(self):
        rules = {"type": [{"field": "v", "kind": "number"}],
                 "bounds": [{"field": "v", "max": 4}],
                 "keyed_bounds": [{"field": "v", "key": "k", "table": "t", "max_path": "limit"}],
                 "keyed_enums": [{"field": "e", "key": "k", "table": "t", "values_path": "options"}]}
        refs = {"t": {"a": {"limit": True, "options": "abc"}}}
        self.assertEqual(evaluate(rules, {"v": 2, "e": "a", "k": "a"}, refs),
                         ["e: keyed enum values are not a collection", "v: keyed bounds limit is not a number"])
        self.assertEqual(evaluate(rules, {"v": float("nan"), "k": "missing"}, refs),
                         ["v: type must be number", "v: bounds require a finite number", "v: keyed bounds require a finite number"])

    def test_real_rules_and_sealed_goldens_are_reproduced(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_rules.py"),
                                 str(ROOT / "examples" / "rules")], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 error", result.stdout.lower())

    def test_engine_meets_existing_contract_budget(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_budgets.py"),
                                 str(ROOT / "knowledge" / "contracts"), "--repo-root", str(ROOT),
                                 "--contract", "validate-rules"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
