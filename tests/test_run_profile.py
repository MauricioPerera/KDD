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
