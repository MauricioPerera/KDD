"""The real baseline CLI must separate reviewed candidates from approved refs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_baseline_risk_review import ReviewFixture, ROOT


class BaselineReviewEntrypointTests(ReviewFixture, unittest.TestCase):
    def cli(self, *args, script='quality_baseline.py'):
        return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / script),
            '--repo-root', str(self.root), *args], capture_output=True,
            encoding='utf-8', timeout=90, env=dict(os.environ, PYTHONUTF8='1'))

    def write_receipt(self, row):
        path = self.owner / 'review.json'
        path.write_text(json.dumps(row), encoding='utf-8')
        return str(path)

    def arguments(self, row=None):
        return ['--base-ref', self.base, '--candidate-ref', self.head,
                '--review', self.write_receipt(self.receipt() if row is None else row)]

    def test_legacy_approved_policy_manifest_preserves_its_real_hashes(self):
        self.candidate()
        result = self.cli('--policy', 'quality.json', '--approved-ref', self.base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['approved_ref'], self.base)
        self.assertEqual(set(data), {'approved_ref', 'policy', 'policy_sha256', 'protected'})
        self.assertIn('tests/oracle.py', data['protected'])
        self.assertNotIn('review_ready', data)

    def test_prebaseline_mode_returns_readiness_without_approving_or_writing(self):
        self.candidate()
        before = self.snapshot()
        result = self.cli(*self.arguments())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['review_ready'])
        self.assertEqual(data['candidate_commit'], self.head)
        self.assertNotIn('approved_ref', data)
        self.assertEqual(self.snapshot(), before)

    def test_incomplete_and_mixed_modes_fail_without_emitting_a_manifest(self):
        self.candidate()
        complete = self.arguments()
        cases = [complete[:2], complete[2:4], complete[4:], complete[:4],
                 complete + ['--policy', 'quality.json', '--approved-ref', self.base],
                 complete + ['--policy', 'quality.json'],
                 ['--approved-ref', self.base], ['--policy', 'quality.json']]
        for args in cases:
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), '')

    def test_absent_reviewer_produces_not_ready_instead_of_legacy_success(self):
        self.candidate()
        row = self.receipt()
        row['reviews'][0]['status'] = 'not_run'
        result = self.cli(*self.arguments(row))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['review_ready'])
        self.assertIn('REVIEW_INCOMPLETE', [item['code'] for item in data['findings']])
        self.assertNotIn('approved_ref', data)

    def test_a_receipt_from_a_different_commit_or_broken_json_is_not_ignored(self):
        self.candidate()
        row = self.receipt()
        row['candidate_commit'] = self.base
        result = self.cli(*self.arguments(row))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('REVIEW_IDENTITY', result.stderr)
        self.assertEqual(result.stdout.strip(), '')
        args = self.arguments()
        Path(args[-1]).write_text('{', encoding='utf-8')
        result = self.cli(*args)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('REVIEW_SCHEMA', result.stderr)
        self.assertEqual(result.stdout.strip(), '')

    def test_inspect_and_verify_commands_have_distinct_exit_semantics(self):
        self.candidate()
        inspected = self.cli('--base-ref', self.base, '--candidate-ref', self.head, script='baseline_review.py')
        self.assertEqual(inspected.returncode, 0, inspected.stdout + inspected.stderr)
        self.assertFalse(json.loads(inspected.stdout)['review_ready'])
        ready = self.cli(*self.arguments(), script='baseline_review.py')
        self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
        self.assertTrue(json.loads(ready.stdout)['review_ready'])
        row = self.receipt()
        row['reviews'][0]['lenses'][0]['assessment'] = 'blocked'
        blocked = self.cli(*self.arguments(row), script='baseline_review.py')
        self.assertEqual(blocked.returncode, 1, blocked.stdout + blocked.stderr)
        self.assertFalse(json.loads(blocked.stdout)['review_ready'])

    def test_legacy_mode_still_rejects_a_branch_alias(self):
        self.candidate()
        before = self.snapshot()
        result = self.cli('--policy', 'quality.json', '--approved-ref', 'HEAD')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('REJECT baseline:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(result.stdout.strip(), '')
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
