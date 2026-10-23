"""Frozen public CLI oracle; uses Git repositories, not mocked persistence."""
import json
import subprocess
import sys
import unittest

import tests.test_task_git as fixtures


class TaskCliTests(unittest.TestCase):
    def setUp(self):
        self.repo = fixtures.Repository()
        self.addCleanup(self.repo.close)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(self.repo.root / 'scripts/tasks.py'),
                               '--repo-root', str(self.repo.root), *args],
                              capture_output=True, text=True, timeout=30)

    def test_create_ready_start_and_json_queries(self):
        for args in [('create', 'TASK-001', '--title', 'Value', '--description', 'Validate input',
                      '--contract', self.repo.contract),
                     ('ready', 'TASK-001', '--approved-ref', self.repo.approved),
                     ('start', 'TASK-001', '--assignee', 'developer')]:
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.run_cli('show', 'TASK-001', '--json')
        self.assertEqual(json.loads(result.stdout)['status'], 'in_progress')
        self.assertEqual(len(json.loads(self.run_cli('list', '--json').stdout)), 1)
        history = json.loads(self.run_cli('history', 'TASK-001', '--json').stdout)
        self.assertEqual([item['status'] for item in history], ['backlog', 'ready', 'in_progress'])

    def test_invalid_transition_is_nonzero_and_does_not_commit(self):
        self.repo.act('create')
        before = self.repo.git('rev-parse', 'HEAD')
        result = self.run_cli('finish', 'TASK-001')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ERROR', result.stderr)
        self.assertEqual(self.repo.git('rev-parse', 'HEAD'), before)

    def test_missing_task_and_path_injection_fail_readably(self):
        for task_id in ['TASK-999', '../outside']:
            result = self.run_cli('show', task_id)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
