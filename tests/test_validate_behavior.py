import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import behavior_contract
import validate_behavior


VALID = {"schema": "kdd-behavior/v1", "domain": {"type": "integer", "min": 0, "max": 3}, "cases": {"mode": "exhaustive", "batch_size": 2}, "property": {"op": "eq", "args": [{"var": "result"}, {"op": "mul", "args": [{"var": "input"}, {"const": 2}]}]}}


class BehaviorTests(unittest.TestCase):
    def test_valid_contract(self):
        self.assertEqual(behavior_contract.validate(VALID), [])

    def test_rejects_unknown_operator(self):
        value = json.loads(json.dumps(VALID))
        value["property"]["op"] = "exec"
        self.assertEqual(behavior_contract.validate(value)[-1][0], "BHV_PROPERTY")

    def test_rejects_extra_key(self):
        value = dict(VALID, unsafe=True)
        self.assertTrue(any(rule == "BHV_KEYS" for rule, _ in behavior_contract.validate(value)))

    def test_optional_directory(self):
        self.assertEqual(validate_behavior.findings(os.path.join(ROOT, "missing-behavior")), [])

    def test_finds_invalid_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "double.behavior.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"schema": "wrong"}, handle)
            self.assertTrue(validate_behavior.findings(directory))

    def test_evaluates_without_exec(self):
        self.assertTrue(behavior_contract.evaluate(VALID["property"], 4, 8))
        self.assertFalse(behavior_contract.evaluate(VALID["property"], 4, 9))


if __name__ == "__main__":
    unittest.main()
