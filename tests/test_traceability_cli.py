"""Real CLI processes and product-policy execution without mocked outcomes."""
import json
from pathlib import Path
import re
import sys
import unittest
from tests import test_traceability_model as support


class TraceabilityCliTests(support.RepositoryFixture):
    def test_json_reports_complete_chain_and_preserves_git_state(self):
        before = support.git(self.root, 'status', '--porcelain=v1')
        p = self.cli('--require-verified')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = self.json_result(p)
        self.assertTrue(report['ok'])
        self.assertTrue(report['complete'])
        self.assertEqual(report['observed_commit'], self.refs['closed'])
        self.assertEqual(report['requirements'][0]['links'][0]['tested_commit'], self.refs['tested'])
        self.assertEqual(support.git(self.root, 'status', '--porcelain=v1'), before)
        self.assertEqual(support.git(self.root, 'branch', '--show-current'), 'main')

    def test_markdown_has_the_same_identities_and_evidence_as_json(self):
        p = self.cli('--require-verified')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = self.json_result(p)
        p = self.cli('--format', 'markdown', '--require-verified')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        link = report['requirements'][0]['links'][0]
        for token in ['REQ-001', 'verified', 'TASK-001', link['tested_commit'], link['evidence'], link['contract'], link['oracle']]:
            self.assertIn(token, p.stdout)
        self.assertRegex(p.stdout, r'(?m)^\|.*REQ-001.*\|')

    def test_external_cwd_and_task_branch_still_query_main(self):
        support.git(self.root, 'switch', '-q', '-c', 'work-in-progress')
        support.write(self.root, 'src/value.py', 'raise RuntimeError("must not execute")\n')
        before = support.git(self.root, 'status', '--porcelain=v1')
        p = self.cli(cwd=Path(self.temp.name))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.json_result(p)['observed_commit'], self.refs['closed'])
        self.assertEqual(support.git(self.root, 'branch', '--show-current'), 'work-in-progress')
        self.assertEqual(support.git(self.root, 'status', '--porcelain=v1'), before)

    def test_pending_plan_is_not_a_strict_approval(self):
        plan = self.plan()
        plan['bindings'][0]['tasks'] = []
        self.save_plan(plan)
        p = self.cli()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = self.json_result(p)
        self.assertTrue(report['ok'])
        self.assertFalse(report['complete'])
        self.assertEqual(report['requirements'][0]['state'], 'pending')
        p = self.cli('--require-verified')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        report = self.json_result(p)
        self.assertFalse(report['ok'])
        self.assertFalse(report['complete'])
        self.assertIn('TRACE_PENDING', [f['code'] for f in report['findings']])

    def test_current_drift_fails_but_historical_ref_is_available(self):
        support.write(self.root, 'src/value.py', support.IMPLEMENTATION + '\n# changed later\n')
        support.commit(self.root, 'new source revision')
        p = self.cli('--require-verified')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        report = self.json_result(p)
        self.assertIn('TRACE_STALE', [f['code'] for f in report['findings']])
        p = self.cli('--ref', self.refs['closed'], '--require-verified')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(self.json_result(p)['complete'])

    def test_missing_manifest_is_error_two_and_never_skip(self):
        p = self.cli('--manifest', 'quality/absent.json')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        report = self.json_result(p)
        self.assertFalse(report['ok'])
        self.assertFalse(report['complete'])
        self.assertIn('TRACE_INPUT', [f['code'] for f in report['findings']])
        self.assertNotIn('SKIP', p.stdout)

    def test_invalid_json_is_structured_input_error(self):
        support.write(self.root, 'quality/traceability.json', '{broken\n')
        support.commit(self.root, 'invalid input JSON')
        p = self.cli()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        report = self.json_result(p)
        self.assertFalse(report['ok'])
        self.assertIn('TRACE_SCHEMA', [f['code'] for f in report['findings']])

    def test_help_and_invalid_arguments_have_conventional_exit_codes(self):
        p = self.cli('--help')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for flag in ['--ref', '--manifest', '--format', '--require-verified']:
            self.assertIn(flag, p.stdout)
        p = self.cli('--unknown-option')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn('usage:', p.stderr.lower())

    def test_real_product_policy_runs_all_three_checks_twice(self):
        p = support.command(self.root, [sys.executable, 'scripts/verify_quality.py', '--repo-root', '.',
                                        '--policy', 'quality/product.json', '--approved-ref', self.refs['approved']])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('PASS quality: integrity, perimeter and all checks verified twice', p.stdout)
        for name in ['product-functional', 'product-adversarial', 'requirements-traceability']:
            self.assertEqual(len(re.findall(r'RUN [12]/2 ' + name + r' \[', p.stdout)), 2)
        self.assertEqual(support.git(self.root, 'status', '--porcelain=v1'), '')

    def test_stale_evidence_blocks_quality_even_when_product_tests_still_pass(self):
        support.write(self.root, 'src/value.py', support.IMPLEMENTATION + '\n# behavior preserved but not the tested revision\n')
        support.commit(self.root, 'different source with the same product behavior')
        product = support.command(self.root, [sys.executable, '-m', 'unittest', 'tests/test_value.py'])
        self.assertEqual(product.returncode, 0, product.stdout + product.stderr)
        p = support.command(self.root, [sys.executable, 'scripts/verify_quality.py', '--repo-root', '.',
                                        '--policy', 'quality/product.json', '--approved-ref', self.refs['approved']])
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('RUN 1/2 requirements-traceability', p.stdout)
        self.assertIn('TRACE_STALE', p.stdout + p.stderr)
        self.assertIn('Check failed: requirements-traceability', p.stderr)

    def test_documented_recipe_contains_strict_check_and_protected_dependencies(self):
        text = (support.ROOT / 'examples/traceability/README.md').read_text(encoding='utf-8')
        self.assertIn('--require-verified', text)
        self.assertIn('quality/product.json', text)
        self.assertIn('required_kinds', text)
        for name in [*support.NEW_MODULES, *support.TASK_MODULES]:
            self.assertIn('scripts/' + name, text)
        template = (support.ROOT / 'templates/PRODUCT-SPEC.md').read_text(encoding='utf-8')
        self.assertIn('## Requisitos', template)
        self.assertIn('[REQ-001]', template)


if __name__ == '__main__':
    unittest.main()
