"""Exercise task_evidence through real Git closures and a Board process."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_task_git import Repository
from tests.test_generated_task_evidence import TaskProject
import oracle_execution
import task_git as journal
from task_model import TaskError
from validate_tasks import validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
NODE_ORACLE = 'tests/nested/value.test.mjs'
NODE_CASE = (
    "import {test} from 'node:test';\n"
    "import assert from 'node:assert/strict';\n"
    "test('value', () => assert.equal(7, 7));\n"
)
EARLY_EXIT = (
    "import os, sys\n"
    "sys.stderr.write('Ran 1 test in 0.001s\\n\\nOK\\n')\n"
    "sys.stderr.flush()\n"
    "os._exit(0)\n"
)


class TaskOracleProof(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.addCleanup(self.repo.close)
        self.contract = self.repo.root / self.repo.contract

    def write(self, name, body):
        target = self.repo.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding='utf-8', newline='\n')

    def approve_node(self, text):
        self.write(NODE_ORACLE, text)
        contract = self.contract.read_text(encoding='utf-8')
        contract = contract.replace('python -m unittest tests/test_value.py', 'node --test ' + NODE_ORACLE)
        contract = contract.replace('tests: tests/test_value.py', 'tests: ' + NODE_ORACLE)
        contract = contract.replace(sha256(self.repo.oracle.encode()).hexdigest(), sha256(text.encode()).hexdigest())
        self.write(self.repo.contract, contract)
        self.repo.approved = self.repo.commit('Approve Node oracle')

    def integrate_early_exit(self):
        self.repo.git('switch', '-q', 'task/TASK-001')
        self.write('src/value.py', EARLY_EXIT)
        self.repo.commit('Synthetic early exit in implementation')
        self.repo.git('switch', '-q', 'main')
        self.repo.git('merge', '--no-ff', '-qm', 'integrate TASK-001', 'task/TASK-001')

    def assert_blocked_close(self):
        head = self.repo.git('rev-parse', 'HEAD')
        files = set((self.repo.root / 'docs/task-evidence').glob('*.json'))
        with self.assertRaisesRegex(TaskError, 'TASK_TESTS'):
            self.repo.act('finish')
        self.assertEqual(self.repo.git('rev-parse', 'HEAD'), head)
        self.assertEqual(journal.read_tasks(self.repo.root)['TASK-001']['status'], 'in_progress')
        self.assertEqual(set((self.repo.root / 'docs/task-evidence').glob('*.json')), files)

    def finish(self):
        task = self.repo.act('finish')['task']
        report = json.loads((self.repo.root / task['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(task['status'], 'done')
        self.assertEqual(validate_snapshot(self.repo.root), [])
        return task, report

    def replace_receipt(self, task, report):
        payload = json.dumps(report, sort_keys=True, separators=(',', ':')) + '\n'
        self.write(task['evidence'], payload)
        node_path = 'knowledge/tasks/TASK-001.md'
        node = (self.repo.root / node_path).read_text(encoding='utf-8')
        self.write(node_path, node.replace(task['evidence_sha256'], sha256(payload.encode()).hexdigest()))
        self.repo.commit('Snapshot receipt fixture')

    def test_empty_node_oracle_cannot_publish_evidence(self):
        self.approve_node('// The file registers no test cases.\n')
        self.repo.start()
        self.repo.integrate()
        self.assert_blocked_close()

    def test_unchanged_python_oracle_cannot_accredit_an_early_exit(self):
        self.repo.start()
        self.integrate_early_exit()
        self.assertEqual((self.repo.root / 'tests/test_value.py').read_text(encoding='utf-8'), self.repo.oracle)
        self.assert_blocked_close()

    def test_real_node_case_is_recorded_per_file(self):
        self.approve_node(NODE_CASE)
        self.repo.start()
        self.repo.integrate()
        _, report = self.finish()
        self.assertEqual(report['schema_version'], 2)
        self.assertEqual(report['passed_tests'], 1)
        self.assertEqual(report['oracle_results'], {NODE_ORACLE: {'executed': 1, 'skipped': 0, 'ok': True}})

    def test_python_close_keeps_utf8_mode_in_the_isolated_oracle(self):
        oracle_path = 'tests/test_value.py'
        body = self.repo.oracle + (
            '\nimport sys\nfrom pathlib import Path\n'
            'class Encoding(unittest.TestCase):\n'
            ' def test_utf8(self):\n'
            '  self.assertEqual(sys.flags.isolated, 1)\n'
            '  self.assertEqual(sys.flags.utf8_mode, 1)\n'
            '  self.assertEqual(Path("src/label.txt").read_text(), chr(0x2603))\n'
        )
        self.write(oracle_path, body)
        self.write('src/label.txt', chr(0x2603))
        contract = self.contract.read_text(encoding='utf-8').replace(
            sha256(self.repo.oracle.encode()).hexdigest(), sha256(body.encode()).hexdigest())
        self.write(self.repo.contract, contract)
        self.repo.approved = self.repo.commit('Approve oracle that reads UTF-8')
        self.repo.start()
        self.repo.integrate()
        with patch.dict(os.environ, {'LC_ALL': 'C.UTF-8'}):
            _, report = self.finish()
        self.assertEqual(report['oracle_results'], {
            oracle_path: {'executed': 2, 'skipped': 0, 'ok': True},
        })

    def test_a_mixed_python_class_skip_cannot_accredit_a_close(self):
        body = self.repo.oracle + (
            '\nclass Omitted(unittest.TestCase):\n'
            ' @classmethod\n'
            ' def setUpClass(cls): raise unittest.SkipTest("fixture omitted class")\n'
            ' def test_never_runs(self): self.fail()\n'
        )
        self.write('tests/test_value.py', body)
        contract = self.contract.read_text(encoding='utf-8').replace(
            sha256(self.repo.oracle.encode()).hexdigest(), sha256(body.encode()).hexdigest())
        self.write(self.repo.contract, contract)
        self.repo.approved = self.repo.commit('Approve fixture with one omitted class')
        self.repo.start()
        self.repo.integrate()
        self.assert_blocked_close()

    def test_shared_python_instrument_rejects_a_class_skip_next_to_real_case(self):
        oracle = 'tests/test_value.py'
        self.write(oracle, self.repo.oracle + (
            '\nclass Omitted(unittest.TestCase):\n'
            ' @classmethod\n'
            ' def setUpClass(cls): raise unittest.SkipTest("fixture omitted class")\n'
            ' def test_never_runs(self): self.fail()\n'
        ))
        outcome = oracle_execution.execute_oracle({
            'test_command': 'python -m unittest ' + oracle, 'test_runner': 'python-unittest',
            'tests': oracle, 'oracle_files': [oracle],
        }, self.repo.root)
        self.assertFalse(outcome['ok'], outcome)
        self.assertEqual(outcome['executed_tests'], 0, outcome)

    def test_quality_reads_an_instrumented_receipt_with_its_frozen_bundle(self):
        with tempfile.TemporaryDirectory(prefix='kdd-v2-quality-') as directory:
            project = TaskProject(Path(directory) / 'project')
            _, result = project.complete(1)
            task = result['task']
            report = json.loads((project.root / task['evidence']).read_text(encoding='utf-8'))
            approval = project.quality()
            self.assertEqual(approval.returncode, 0, approval.stdout + approval.stderr)
            self.assertEqual(approval.stdout.count('RUN '), 4)
            self.assertEqual(report['schema_version'], 2)
            self.assertEqual(report['oracle_results'], {
                'tests/test_feature1.py': {'executed': 2, 'skipped': 0, 'ok': True},
            })

    def test_historical_receipt_still_validates_without_running_oracle(self):
        self.repo.start()
        self.repo.integrate()
        completed = subprocess.run(
            [sys.executable, '-m', 'unittest', 'tests/test_value.py'],
            cwd=self.repo.root, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        task, report = self.finish()
        output = completed.stdout + completed.stderr
        report.update(schema_version=1, runner='unittest', stdout=completed.stdout,
                      stderr=completed.stderr, output_sha256=sha256(output.encode()).hexdigest())
        report.pop('oracle_results', None)
        self.replace_receipt(task, report)
        self.write('tests/test_value.py', 'raise RuntimeError("historical audit must not load checkout")\n')
        self.assertEqual(validate_snapshot(self.repo.root), [])

    def test_schema_two_requires_positive_results_for_every_selected_file(self):
        self.repo.start()
        self.repo.integrate()
        task, report = self.finish()
        valid_row = {'executed': 1, 'skipped': 0, 'ok': True}
        invalid = (
            {},
            {'tests/other.py': valid_row},
            {'tests/test_value.py': dict(valid_row, executed=2)},
        )
        for rows in invalid:
            with self.subTest(rows=rows):
                report.update(schema_version=2, oracle_results=rows)
                self.replace_receipt(task, report)
                findings = validate_snapshot(self.repo.root)
                task = journal.read_tasks(self.repo.root)['TASK-001']
                self.assertTrue(any('TASK_EVIDENCE' in item and 'oracle' in item.lower()
                                    for item in findings), findings)

    def test_board_executes_real_node_oracle_and_rejects_empty_wrapper(self):
        env = dict(os.environ)
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        result = subprocess.run(
            ['node', '--test', 'tools/kdd-board/tests/task-oracle-execution-proof.test.ts'],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=45, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
