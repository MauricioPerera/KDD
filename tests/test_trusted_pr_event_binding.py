"""Run the trusted PR guard over local, mutable pull merge references."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_approval_registry import GitApprovalFixture, ROOT

WORKFLOW = ROOT / '.github/workflows/trusted-pr-gate.yml'


class TrustedPREventBinding(GitApprovalFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.origin = cls.root.parent / 'origin.git'
        cls.command('git', 'init', '--bare', '-q', str(cls.origin))
        cls.command('git', 'remote', 'add', 'origin', str(cls.origin))
        base, one, two = (cls.refs[name] for name in ('main', 'one', 'two'))
        main_tree = cls.trees['main']
        next_base = cls.command('git', 'commit-tree', main_tree, '-p', base, '-m', 'main advanced')
        cls.candidates = {
            'event': cls.refs['merge'],
            'new_head': cls.command('git', 'commit-tree', cls.trees['two'], '-p', base, '-p', two, '-m', 'new head'),
            'new_base': cls.command('git', 'commit-tree', cls.trees['one'], '-p', next_base, '-p', one, '-m', 'new base'),
            'swapped': cls.command('git', 'commit-tree', cls.trees['one'], '-p', one, '-p', base, '-m', 'swapped'),
            'linear': one,
        }

    def invoke(self, candidate, *, base=None, head=None, registry=None, workflow=True):
        self.command('git', 'push', '-qf', 'origin', self.candidates[candidate] + ':refs/pull/7/merge')
        args = [sys.executable, str(ROOT / 'scripts/guard_pr_baseline.py'), '--pr-number', '7',
                '--base-ref', self.refs['main'] if base is None else base,
                '--approval-registry', json.dumps(self.records() if registry is None else registry)]
        workflow_text = WORKFLOW.read_text(encoding='utf-8')
        if workflow and '--head-ref' in workflow_text:
            args.extend(['--head-ref', self.refs['one'] if head is None else head])
        env = dict(os.environ, PYTHONUTF8='1')
        env.pop('KDD_TRUSTED_CHANGE_REVIEW', None)
        return subprocess.run(args, cwd=self.root, capture_output=True, text=True,
                              encoding='utf-8', timeout=60, env=env)

    def test_workflow_supplies_exact_trusted_base_and_event_head(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('ref: ${{ github.event.pull_request.base.sha }}', workflow)
        self.assertIn('HEAD_SHA: ${{ github.event.pull_request.head.sha }}', workflow)
        self.assertIn('--head-ref "$HEAD_SHA"', workflow)
        self.assertIn('contents: read', workflow)

    def test_matching_merge_keeps_existing_approval(self):
        before = self.command('git', 'rev-parse', 'HEAD')
        result = self.invoke('event')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS: trusted PR baseline', result.stdout)
        self.assertEqual(self.command('git', 'rev-parse', 'HEAD'), before)

    def test_remote_move_with_approved_tree_cannot_approve_another_head(self):
        self.assertEqual(self.invoke('event').returncode, 0)
        result = self.invoke('new_head')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('PR_EVENT_MISMATCH', result.stdout)

    def test_same_head_with_advanced_base_is_rejected_before_registry(self):
        result = self.invoke('new_base', registry={'bad': 'registry'})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('PR_EVENT_MISMATCH', result.stdout)

    def test_nonmerge_and_reversed_parents_are_rejected(self):
        for candidate in ('linear', 'swapped'):
            with self.subTest(candidate=candidate):
                result = self.invoke(candidate)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('PR_EVENT_MISMATCH', result.stdout)

    def test_symbolic_base_abbreviated_head_and_missing_head_are_rejected(self):
        for inputs in ({'base': 'main'}, {'head': self.refs['one'][:12]}, {'workflow': False}):
            with self.subTest(inputs=inputs):
                result = self.invoke('event', **inputs)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('PASS:', result.stdout)


if __name__ == '__main__':
    unittest.main()
