"""Exercise strict product approval against original commits and real oracles."""

import json
from pathlib import Path
import sys
import unittest

from tests import test_quality_oracle_reviews as fixtures

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/validate.yml'


class QualityFixture(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.QualityOracleReviews()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def run_gate(self, strict):
        import subprocess
        argv = [sys.executable, str(ROOT / 'scripts/verify_quality.py'),
                '--repo-root', str(self.fixture.root), '--policy', 'quality/product.json',
                '--approved-ref', self.fixture.ref]
        if strict:
            argv.append('--require-oracle-reviews')
        return subprocess.run(argv, capture_output=True, text=True, encoding='utf-8',
                              timeout=90)

    def freeze_noop_policy(self):
        self.fixture.policy.pop('oracle_reviews')
        for check in self.fixture.policy['checks']:
            check['argv'] = [sys.executable, '-c', 'pass']
        self.fixture.freeze()



class QualityRequiredOracleEvidence(QualityFixture):
    def test_strict_mode_rejects_the_historical_false_green(self):
        import subprocess
        self.freeze_noop_policy()
        self.fixture.write('src/app.py', fixtures.MUTANT)
        actual = subprocess.run([sys.executable, '-m', 'unittest', fixtures.CASE],
                                cwd=self.fixture.root, capture_output=True, timeout=20)
        self.assertEqual(actual.returncode, 1)
        self.assertIn(b'AssertionError', actual.stderr)
        compatible = self.run_gate(strict=False)
        self.assertEqual(compatible.returncode, 0, compatible.stderr)
        self.assertIn('LIMIT quality: oracle assurance not requested', compatible.stdout)
        strict = self.run_gate(strict=True)
        self.assertNotEqual(strict.returncode, 0)
        self.assertIn('ORACLE_REQUIRED', strict.stdout + strict.stderr)
        self.assertNotIn('RUN 1/2', strict.stdout)
        self.assertNotIn('PASS quality', strict.stdout)

    def test_strict_mode_accepts_the_two_real_oracle_reviews(self):
        outcome = self.run_gate(strict=True)
        self.assertEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
        reports = [json.loads(row.removeprefix('ORACLE_REVIEW '))
                   for row in outcome.stdout.splitlines() if row.startswith('ORACLE_REVIEW ')]
        self.assertEqual([row['iteration'] for row in reports], [1, 2])
        for report in reports:
            self.assertEqual(report['approved_ref'], self.fixture.ref)
            self.assertEqual(report['mutants'][0]['failed_tests'], [fixtures.CASE])
            self.assertEqual(report['mutants'][0]['status'], 'DETECTED')

    def test_strict_mode_propagates_a_real_failed_oracle(self):
        self.fixture.write('src/app.py', fixtures.MUTANT)
        outcome = self.run_gate(strict=True)
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn('ORACLE_CONTROL', outcome.stdout + outcome.stderr)
        self.assertNotIn('PASS quality', outcome.stdout)
        self.assertFalse((self.fixture.root / 'checks.txt').exists())


class QualityEvidenceWorkflow(unittest.TestCase):
    def test_reusable_workflow_exposes_the_strict_mode(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        step = text.split('      - name: Approve project quality (when configured)\n', 1)[1]
        step = step.split('      - name:', 1)[0]
        self.assertIn('quality_require_oracle_reviews:', text)
        self.assertIn('KDD_QUALITY_REQUIRE_ORACLE_REVIEWS', step)
        self.assertIn('--require-oracle-reviews', step)

    def test_bootstrap_defaults_to_strict_and_uses_the_approved_runner(self):
        text = generated_workflow()
        declaration = text.split('      quality_require_oracle_reviews:\n', 1)[-1]
        self.assertTrue(declaration.startswith('        type: boolean\n        default: true\n'))
        self.assertIn('vars.KDD_QUALITY_REQUIRE_ORACLE_REVIEWS', text)
        step = text.split('      - name: Approve project quality (when configured)\n', 1)[1]
        step = step.split('      - name:', 1)[0]
        self.assertIn('approved + \':scripts/verify_quality.py\'', step)
        self.assertIn('--require-oracle-reviews', step)



class QualityEvidenceWorkflowExecution(QualityFixture):
    """Execute the generated step against the candidate and the frozen runner."""

    def test_generated_strict_blocks_missing_policy_and_reference(self):
        outcome = self.workflow_gate(True, reference='', policy='missing.json')
        self.assertNotEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
        self.assertNotIn('SKIP:', outcome.stdout)

    def test_generated_strict_uses_approved_runner_and_honors_legacy_opt_out(self):
        self.fixture.policy.pop('oracle_reviews')
        self.freeze_runner()
        compatible = self.workflow_gate(False)
        self.assertEqual(compatible.returncode, 0, compatible.stdout + compatible.stderr)
        self.assertIn('PASS quality:', compatible.stdout)
        self.fixture.write('scripts/verify_quality.py', "print('FAKE_QUALITY_APPROVAL')\n")
        modes = {'generated': generated_workflow(),
                 'native': WORKFLOW.read_text(encoding='utf-8')}
        for mode, text in modes.items():
            with self.subTest(mode=mode):
                strict = self.workflow_gate(True, text=text)
                self.assertNotEqual(strict.returncode, 0, strict.stdout + strict.stderr)
                self.assertIn('ORACLE_REQUIRED', strict.stdout + strict.stderr)
                self.assertNotIn('FAKE_QUALITY_APPROVAL', strict.stdout)

    def test_generated_strict_executes_both_oracle_reviews(self):
        self.freeze_runner()
        outcome = self.workflow_gate(True)
        self.assertEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
        self.assertEqual(outcome.stdout.count('ORACLE_REVIEW '), 2)

    def test_strict_step_cannot_use_a_replacement_executor(self):
        self.freeze_runner()
        approved = self.fixture.ref
        self.fixture.write('scripts/verify_quality.py', "print('REPLACEMENT_EXECUTOR')\n")
        self.fixture.git('add', 'scripts/verify_quality.py')
        self.fixture.git('commit', '-qm', 'Create replacement executor')
        replacement = self.fixture.git('rev-parse', 'HEAD')
        self.fixture.git('reset', '--hard', approved)
        self.fixture.git('replace', approved, replacement)
        modes = {'generated': generated_workflow(),
                 'native': WORKFLOW.read_text(encoding='utf-8')}
        for mode, text in modes.items():
            with self.subTest(mode=mode):
                marker = self.fixture.root / 'checks.txt'
                marker.unlink(missing_ok=True)
                result = self.workflow_gate(True, reference=approved, text=text)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('REPLACEMENT_EXECUTOR', result.stdout)
                self.assertEqual(result.stdout.count('ORACLE_REVIEW '), 2)

    def test_native_strict_step_rejects_missing_configuration(self):
        outcome = self.workflow_gate(True, reference='', policy='missing.json',
                                     text=WORKFLOW.read_text(encoding='utf-8'))
        self.assertNotEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
        self.assertNotIn('SKIP:', outcome.stdout)

    def freeze_runner(self):
        runner = ROOT / 'scripts/verify_quality.py'
        self.fixture.write('scripts/verify_quality.py', runner.read_text(encoding='utf-8'))
        self.fixture.policy['protected'].append('scripts/verify_quality.py')
        self.fixture.freeze()

    def workflow_gate(self, strict, *, reference=None, policy='quality/product.json', text=None):
        import os
        import subprocess
        import textwrap

        text = generated_workflow() if text is None else text
        step = text.split('      - name: Approve project quality (when configured)\n', 1)[1]
        step = step.split('      - name:', 1)[0]
        body = textwrap.dedent(step.split('        run: |\n', 1)[1])
        env = dict(os.environ, KDD_QUALITY_POLICY=policy,
                   KDD_QUALITY_APPROVED_REF=self.fixture.ref if reference is None else reference,
                   KDD_QUALITY_REQUIRE_ORACLE_REVIEWS=str(strict).lower())
        return subprocess.run([sys.executable, '-c', body], cwd=self.fixture.root,
                              env=env, capture_output=True, text=True, encoding='utf-8',
                              timeout=90)


def generated_workflow():
    text = WORKFLOW.read_text(encoding='utf-8')
    if 'Check product quality approval configuration' in text:
        return text
    sys.path.insert(0, str(ROOT / 'scripts'))
    from init_project import _product_quality_ci
    return _product_quality_ci(ROOT).decode('utf-8').replace('\r\n', '\n')
