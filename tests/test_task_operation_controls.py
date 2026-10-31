"""Independent real-Git oracle for task and product operation controls."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_generated_task_evidence import ROOT, TaskProject
from tests.test_task_finish_perimeter import PerimeterProject

sys.path.insert(0, str(ROOT / 'scripts'))
import task_git as journal
from task_model import TaskError


class OperationControlTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-operation-controls-')
        self.addCleanup(self.area.cleanup)
        self.p = PerimeterProject(Path(self.area.name) / 'product')
        self.marker = Path(self.area.name) / 'oracle-ran.txt'
        self.p.env['KDD_PERIMETER_PROBE'] = str(self.marker)

    def change_contract(self, transform):
        name = self.p.contract(1)
        self.p.write(name, transform((self.p.root / name).read_text(encoding='utf-8')))
        self.p.ref = self.p.commit('Synthetic reviewed control contract')

    def backlog(self):
        self.p.act('create', 1, '--title', 'Control fixture', '--description',
                   'Synthetic operation control', '--contract', self.p.contract(1))

    def legacy_ready(self):
        self.backlog()
        node = 'knowledge/tasks/TASK-001.md'
        sys.path.insert(0, str(ROOT / 'scripts'))
        from task_model import render_task
        from validate_contracts import parse_frontmatter
        data, body = parse_frontmatter((self.p.root / node).read_text(encoding='utf-8'))
        data.update(status='ready', approved_ref=self.p.ref, reason='Synthetic old coordinator')
        self.p.write(node, render_task(data, body))
        self.p.commit('Synthetic old ready transition')

    def legacy_start(self):
        self.legacy_ready()
        node = 'knowledge/tasks/TASK-001.md'
        from task_model import render_task
        from validate_contracts import parse_frontmatter
        data, body = parse_frontmatter((self.p.root / node).read_text(encoding='utf-8'))
        data.update(status='in_progress', assignee='synthetic old worker',
                    branch_base=self.p.git('rev-parse', 'HEAD'), reason='Synthetic old start')
        self.p.git('branch', data['branch'], data['branch_base'])
        self.p.write(node, render_task(data, body))
        self.p.commit('Synthetic old start transition')
        self.p.implement(1)

    def rejected(self, operation, code):
        args = {'ready': ['--approved-ref', self.p.ref],
                'start': ['--assignee', 'synthetic worker'], 'finish': []}[operation]
        before = self.p.snapshot()
        result = self.p.act(operation, 1, *args, check=False)
        self.assertNotEqual(result.returncode, 0, operation + ' accepted a missing required control')
        self.assertIn(code, result.stdout + result.stderr)
        self.assertEqual(self.p.snapshot(), before)
        self.assertFalse(self.marker.exists(), 'oracle executed before rejection')
        self.assertEqual(list((self.p.root / 'docs/task-evidence').glob('*.json')), [])

    def command(self, value):
        self.change_contract(lambda text: text.replace(
            'python -m unittest tests/test_feature1.py', value))

    def malformed(self):
        self.change_contract(lambda text: text.replace('\n## Examples\n', '\n## Explanation\n'))

    def test_ready_rejects_unsupported_runner_before_publishing(self):
        self.command('pytest tests/test_feature1.py')
        self.backlog()
        self.rejected('ready', 'TASK_RUNNER')

    def test_ready_rejects_additional_unittest_arguments(self):
        self.command('python -m unittest tests/test_feature1.py -v')
        self.backlog()
        self.rejected('ready', 'TASK_RUNNER')

    def test_ready_rejects_a_command_for_an_unsealed_other_oracle(self):
        self.command('python -m unittest tests/test_other.py')
        self.backlog()
        self.rejected('ready', 'TASK_RUNNER')

    def test_ready_rejects_recognized_runner_when_its_executable_is_missing(self):
        self.assertIsNone(shutil.which('python3.9999'))
        self.command('python3.9999 -m unittest tests/test_feature1.py')
        self.backlog()
        self.rejected('ready', 'TASK_RUNNER')

    def test_start_rejects_unsupported_runner_in_an_old_ready_node(self):
        self.command('pytest tests/test_feature1.py')
        self.legacy_ready()
        self.rejected('start', 'TASK_RUNNER')

    def test_start_rejects_recognized_runner_when_its_executable_is_missing(self):
        self.assertIsNone(shutil.which('python3.9999'))
        self.command('python3.9999 -m unittest tests/test_feature1.py')
        self.legacy_ready()
        self.rejected('start', 'TASK_RUNNER')

    def test_history_does_not_require_a_past_runner_to_be_installed_today(self):
        self.assertIsNone(shutil.which('python3.9999'))
        self.command('python3.9999 -m unittest tests/test_feature1.py')
        self.legacy_ready()
        before = self.p.snapshot()
        result = self.p.command([sys.executable, 'scripts/validate_tasks.py',
                                '--repo-root', str(self.p.root), '--head-ref', 'HEAD'], check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.p.snapshot(), before)
        self.assertFalse(self.marker.exists())

    def test_start_rejects_structurally_incomplete_old_ready_contract(self):
        self.malformed()
        self.legacy_ready()
        self.rejected('start', 'TASK_CONTRACT')

    def test_finish_rejects_structurally_incomplete_old_contract_before_oracle(self):
        self.malformed()
        self.legacy_start()
        self.rejected('finish', 'TASK_CONTRACT')

    def test_finish_classifies_a_missing_required_executable_as_runner_unavailable(self):
        self.assertIsNone(shutil.which('python3.9999'))
        self.command('python3.9999 -m unittest tests/test_feature1.py')
        self.legacy_start()
        self.rejected('finish', 'TASK_RUNNER')

    def test_snapshot_rejects_incomplete_ready_contract_using_only_git(self):
        self.malformed()
        self.legacy_ready()
        valid_checkout = self.p.contract_text(1, self.p.oracle(1))
        self.p.write(self.p.contract(1), valid_checkout)
        before = self.p.snapshot()
        result = self.p.command([sys.executable, 'scripts/validate_tasks.py',
                                '--repo-root', str(self.p.root), '--head-ref', 'HEAD'], check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('TASK_CONTRACT', result.stdout + result.stderr)
        self.assertEqual(self.p.snapshot(), before)
        self.assertFalse(self.marker.exists())

    def test_ready_still_rejects_a_structurally_incomplete_contract(self):
        self.malformed()
        self.backlog()
        self.rejected('ready', 'TASK_CONTRACT')

    def test_recognized_python_can_be_ready_and_started_without_running_oracle(self):
        self.p.create(1)
        self.assertFalse(self.marker.exists())
        result = self.p.act('start', 1, '--assignee', 'synthetic worker')
        self.assertEqual(result['task']['status'], 'in_progress')
        self.assertFalse(self.marker.exists())

    def test_recognized_node_can_be_ready_and_started_without_running_oracle(self):
        oracle = ("const {test}=require('node:test');const assert=require('node:assert/strict');"
                  "const fs=require('node:fs');if(process.env.KDD_PERIMETER_PROBE)"
                  "fs.writeFileSync(process.env.KDD_PERIMETER_PROBE,'executed');"
                  "test('source',()=>assert.ok(fs.readFileSync('src/feature1.py','utf8').includes('def f1')));\n")
        self.p.write('tests/feature1.test.cjs', oracle)
        previous = hashlib.sha256(self.p.oracle(1).encode()).hexdigest()
        self.change_contract(lambda text: text.replace('tests/test_feature1.py', 'tests/feature1.test.cjs')
                             .replace('python -m unittest tests/feature1.test.cjs',
                                      'node --test tests/feature1.test.cjs')
                             .replace(previous, hashlib.sha256(oracle.encode()).hexdigest()))
        self.p.create(1)
        self.p.act('start', 1, '--assignee', 'synthetic worker')
        self.assertFalse(self.marker.exists())

    def test_full_python_lifecycle_keeps_real_passing_evidence(self):
        self.p.create(1)
        self.p.act('start', 1, '--assignee', 'synthetic worker')
        self.p.implement(1)
        result = self.p.act('finish', 1)
        report = json.loads((self.p.root / result['task']['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(report['passed_tests'], 2)
        self.assertTrue(self.marker.exists())

    def test_public_python_mutation_cannot_bypass_ready_runner_control(self):
        self.command('pytest tests/test_feature1.py')
        self.backlog()
        before = self.p.snapshot()
        with patch.dict(os.environ, self.p.env, clear=True):
            with self.assertRaisesRegex(TaskError, 'TASK_RUNNER'):
                journal.mutate(self.p.root, 'ready', 'TASK-001', {'approved_ref': self.p.ref})
        self.assertEqual(self.p.snapshot(), before)
        self.assertFalse(self.marker.exists())


class ProductControlTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-product-controls-')
        self.addCleanup(self.area.cleanup)
        self.p = TaskProject(Path(self.area.name) / 'product')
        self.policy = self.p.policy()
        self.p.write('src/feature1.py', self.p.implementation(1))

    def approve(self):
        self.p.write('quality/product.json', json.dumps(self.policy))
        self.p.ref = self.p.commit('Synthetic policy approval')

    def rejected(self):
        before = self.p.snapshot()
        result = self.p.quality()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('PASS quality:', result.stdout + result.stderr)
        self.assertEqual(self.p.snapshot(), before)
        return result

    def test_product_runs_every_declared_check_twice(self):
        self.approve()
        result = self.p.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for iteration in (1, 2):
            for kind in ('functional', 'adversarial'):
                self.assertIn(f'RUN {iteration}/2 {kind} [{kind}]', result.stdout)
        self.assertIn('PASS quality:', result.stdout)

    def test_product_missing_approved_policy_is_rejected(self):
        self.approve()
        self.p.git('rm', 'quality/product.json')
        self.p.commit('Candidate removes required policy')
        self.rejected()

    def test_product_missing_required_category_is_rejected(self):
        self.policy['required_kinds'].append('ui')
        self.approve()
        self.rejected()

    def test_product_required_check_without_available_executable_is_rejected(self):
        self.policy['checks'][0]['argv'] = ['kdd-deliberately-nonexistent-control-executable']
        self.approve()
        self.rejected()

    def test_product_functional_failure_blocks_approval(self):
        self.policy['checks'][0]['argv'] = [sys.executable, '-c', 'raise SystemExit(17)']
        self.approve()
        result = self.rejected()
        self.assertIn('functional', result.stdout + result.stderr)

    def test_product_adversarial_failure_blocks_approval(self):
        self.policy['checks'][1]['argv'] = [sys.executable, '-c', 'raise SystemExit(19)']
        self.approve()
        result = self.rejected()
        self.assertIn('adversarial', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
