import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import run_profile


class RunProfileTests(unittest.TestCase):
    APPROVED = 'a' * 40

    def test_profiles_are_ordered_and_inclusive(self):
        minimal = run_profile.build_profile("minimal")
        standard = run_profile.build_profile("standard", approved_ref=self.APPROVED)
        strict = run_profile.build_profile("strict", approved_ref=self.APPROVED)

        self.assertLess(len(minimal), len(standard))
        self.assertLess(len(standard), len(strict))
        self.assertEqual([step for step, _ in minimal], ['contracts', 'suite'])
        self.assertEqual([step for step, _ in standard[:3]],
                         ['contracts', 'approved_baseline', 'suite'])
        self.assertEqual(standard, strict[:len(standard)])

    def test_unknown_profile_fails_clearly(self):
        with self.assertRaises(ValueError):
            run_profile.build_profile("experimental")

    def test_mutation_contract_is_strict_only_and_explicit(self):
        with self.assertRaises(ValueError):
            run_profile.build_profile("standard", "knowledge/contracts/task.md")
        profile = run_profile.build_profile("strict", "knowledge/contracts/task.md",
                                            approved_ref=self.APPROVED)
        self.assertEqual(profile[-1][0], "mutation")

    def test_budget_contract_replaces_global_diagnostic(self):
        profile = run_profile.build_profile("strict", budget_contract="task",
                                            approved_ref=self.APPROVED)
        budgets = [command for step, command in profile if step == "budgets"]
        self.assertEqual(len(budgets), 1)
        self.assertEqual(budgets[0][-2:], ("--contract", "task"))

    def test_runner_stops_after_first_failure(self):
        calls = []

        def runner(command, cwd):
            calls.append((command, cwd))
            return 1 if len(calls) == 2 else 0

        result = run_profile.run_profile("standard", "repo", runner=runner,
                                         approved_ref=self.APPROVED)

        self.assertFalse(result["ok"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["failed_at"], "approved_baseline")

    def test_standard_requires_explicit_full_approved_sha(self):
        for value in (None, '', 'HEAD', 'origin/main', 'abc123'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run_profile.build_profile('standard', approved_ref=value)

    def test_standard_runs_baseline_before_contract_tests(self):
        profile = run_profile.build_profile('standard', approved_ref=self.APPROVED)
        names = [step for step, _ in profile]
        self.assertLess(names.index('approved_baseline'), names.index('contract_tests'))
        self.assertLess(names.index('approved_baseline'), names.index('suite'))
        baseline = dict(profile)['approved_baseline']
        self.assertEqual(baseline[-1], self.APPROVED)
        self.assertIn('--all', baseline)

    def test_failed_baseline_never_runs_suite_or_contract_tests(self):
        calls = []

        def runner(command, cwd):
            calls.append(command)
            return 1 if any(part.endswith('validate_baseline.py') for part in command) else 0

        result = run_profile.run_profile('standard', 'repo', runner=runner,
                                         approved_ref=self.APPROVED)
        self.assertEqual(result['failed_at'], 'approved_baseline')
        self.assertEqual([item['step'] for item in result['results']],
                         ['contracts', 'approved_baseline'])

    def test_broken_contract_tests_fail_standard(self):
        def runner(command, cwd):
            return 1 if any(part.endswith('validate_test_commands.py') for part in command) else 0
        result = run_profile.run_profile('standard', 'repo', runner=runner,
                                         approved_ref=self.APPROVED)
        self.assertFalse(result['ok'])
        self.assertEqual(result['failed_at'], 'contract_tests')
        self.assertEqual(result['results'][-1]['status'], 'FAIL')

    def test_optional_missing_evidence_is_skip_not_pass(self):
        def runner(command, cwd):
            output = ('INFO [PATH_MISSING] optional input missing'
                      if any(part.endswith('validate_rules.py') for part in command) else '')
            return {'exit_code': 0, 'output': output}
        result = run_profile.run_profile('standard', 'repo', runner=runner,
                                         approved_ref=self.APPROVED)
        self.assertTrue(result['ok'])
        statuses = {item['step']: item['status'] for item in result['results']}
        self.assertEqual(statuses['rules'], 'SKIP')
        self.assertEqual(statuses['contract_tests'], 'PASS')

    def test_absent_product_contracts_are_reported_as_skip(self):
        def runner(command, cwd):
            output = ('SKIP [product] no contracts with test_command\n'
                      'Summary: product PASS=0 FAIL=0 SKIP=1\n') if any(
                          part.endswith('validate_test_commands.py') for part in command) else ''
            return {'exit_code': 0, 'output': output}
        result = run_profile.run_profile('standard', 'repo', runner=runner,
                                         approved_ref=self.APPROVED)
        item = next(item for item in result['results'] if item['step'] == 'contract_tests')
        self.assertEqual(item['status'], 'SKIP')

    def test_suite_skips_are_counted_separately(self):
        def runner(command, cwd):
            return {'exit_code': 0, 'output': 'OK (skipped=16)\n' if '-m' in command else ''}
        result = run_profile.run_profile('standard', 'repo', runner=runner,
                                         approved_ref=self.APPROVED)
        item = next(item for item in result['results'] if item['step'] == 'suite')
        self.assertEqual(item['status'], 'PASS')
        self.assertEqual(item['skipped_tests'], 16)


if __name__ == "__main__":
    unittest.main()
