import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate_budgets


class ValidateBudgetsTests(unittest.TestCase):
    def _repo(self, contract, source):
        root = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(root.name, "knowledge", "contracts"))
        os.makedirs(os.path.join(root.name, "src"))
        with open(os.path.join(root.name, "knowledge", "contracts", "task.md"), "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent(contract))
        with open(os.path.join(root.name, "src", "task.py"), "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent(source))
        return root

    def test_accepts_source_inside_declared_budget(self):
        repo = self._repo(
            """
            ---
            type: 'Task Contract'
            target: src/task.py
            budget:
              cyclomatic_max: 3
              nesting_max: 2
              lines_max: 12
              params_max: 2
            ---
            """,
            """
            def summarize(value, fallback):
                if value:
                    return value
                return fallback
            """,
        )
        try:
            result = validate_budgets.validate_directory(
                os.path.join(repo.name, "knowledge", "contracts"), repo.name
            )
            self.assertEqual(result, [])
        finally:
            repo.cleanup()

    def test_rejects_complexity_and_parameter_overruns(self):
        repo = self._repo(
            """
            ---
            type: 'Task Contract'
            target: src/task.py
            budget:
              cyclomatic_max: 2
              nesting_max: 1
              params_max: 2
            ---
            """,
            """
            def decide(a, b, c):
                if a and b:
                    return c
                return None
            """,
        )
        try:
            findings = validate_budgets.validate_directory(
                os.path.join(repo.name, "knowledge", "contracts"), repo.name
            )
            rules = {finding.rule for finding in findings}
            self.assertIn("BUDGET_CYCLOMATIC", rules)
            self.assertIn("BUDGET_PARAMS", rules)
        finally:
            repo.cleanup()

    def test_skips_non_python_targets(self):
        with tempfile.TemporaryDirectory() as root:
            contracts = os.path.join(root, "contracts")
            os.makedirs(contracts)
            with open(os.path.join(contracts, "task.md"), "w", encoding="utf-8") as fh:
                fh.write("---\ntype: 'Task Contract'\ntarget: app.ts\nbudget:\n  cyclomatic_max: 1\n---\n")
            self.assertEqual(validate_budgets.validate_directory(contracts, root), [])

    def test_can_scope_validation_to_one_contract(self):
        with tempfile.TemporaryDirectory() as root:
            contracts = os.path.join(root, "contracts")
            os.makedirs(contracts)
            for name in ("good", "bad"):
                with open(os.path.join(contracts, name + ".md"), "w", encoding="utf-8") as fh:
                    fh.write("---\ntype: 'Task Contract'\ntarget: missing.py\nbudget:\n  cyclomatic_max: 1\n---\n")
            self.assertEqual(
                validate_budgets.validate_directory(contracts, root, "good"), []
            )


if __name__ == "__main__":
    unittest.main()
