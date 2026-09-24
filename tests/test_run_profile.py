import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import run_profile


class RunProfileTests(unittest.TestCase):
    def test_profiles_are_ordered_and_inclusive(self):
        minimal = run_profile.build_profile("minimal")
        standard = run_profile.build_profile("standard")
        strict = run_profile.build_profile("strict")

        self.assertLess(len(minimal), len(standard))
        self.assertLess(len(standard), len(strict))
        self.assertEqual(minimal, standard[:len(minimal)])
        self.assertEqual(standard, strict[:len(standard)])

    def test_unknown_profile_fails_clearly(self):
        with self.assertRaises(ValueError):
            run_profile.build_profile("experimental")

    def test_mutation_contract_is_strict_only_and_explicit(self):
        with self.assertRaises(ValueError):
            run_profile.build_profile("standard", "knowledge/contracts/task.md")
        profile = run_profile.build_profile("strict", "knowledge/contracts/task.md")
        self.assertEqual(profile[-1][0], "mutation")

    def test_budget_contract_replaces_global_diagnostic(self):
        profile = run_profile.build_profile("strict", budget_contract="task")
        budgets = [command for step, command in profile if step == "budgets"]
        self.assertEqual(len(budgets), 1)
        self.assertEqual(budgets[0][-2:], ("--contract", "task"))

    def test_runner_stops_after_first_failure(self):
        calls = []

        def runner(command, cwd):
            calls.append((command, cwd))
            return 1 if len(calls) == 2 else 0

        result = run_profile.run_profile("standard", "repo", runner=runner)

        self.assertFalse(result["ok"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["failed_at"], "suite")


if __name__ == "__main__":
    unittest.main()
