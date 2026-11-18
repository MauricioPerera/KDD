"""Measure cold Git reads and exercise live multi-file task transitions."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import test_git_task_multi_oracle as fixture


COLD_ARTIFACTS = '''
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / 'scripts'))
import task_git as journal
from task_model import TaskError

head, trace, contract, oracle, target = sys.argv[1:]
root = Path.cwd()
with journal.object_cache():
    assert journal._native_oid(root, head), 'Git object format must be known'
    os.environ['GIT_TRACE2_EVENT'] = trace
    try:
        journal._finish_artifacts(root, {'contract': contract, 'task_id': 'TASK-001'},
                                  {'tests': oracle, 'target': target}, head)
    except TaskError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
'''

MOVE_TIP = '''
    def test_moves_task_branch_without_touching_the_checkout(self):
        import subprocess

        subprocess.run(['git', 'update-ref', 'refs/heads/task/TASK-001', 'HEAD'],
                       check=True, capture_output=True, timeout=20)
'''


class TaskTransitionReadCost(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-transition-trace-')
        self.addCleanup(area.cleanup)
        self.area = Path(area.name)
        self.builder = fixture.GitTaskMultiOracle()
        self.addCleanup(self.builder.doCleanups)

    def project(self, algorithm='sha1', **options):
        with patch.dict(os.environ, {'GIT_DEFAULT_HASH': algorithm}):
            project = self.builder.project(**options)
        self.assertEqual(project.git('rev-parse', '--show-object-format'), algorithm)
        return project

    def starts(self, trace):
        launches = []
        for line in trace.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            if event.get('event') == 'start':
                launches.append(event['argv'])
        self.assertTrue(launches, 'the operation must execute real Git')
        return launches

    def transition(self, project, operation, *args):
        trace = self.area / (project.root.parent.name + '-' + operation + '.jsonl')
        result = project.command(
            [sys.executable, 'scripts/tasks.py', '--repo-root', str(project.root), operation,
             'TASK-001', *args, '--json'],
            env=dict(project.env, GIT_TRACE2_EVENT=str(trace)), check=False)
        return result, self.starts(trace)

    def assert_identity_read(self, launches):
        first_status = next(i for i, argv in enumerate(launches) if 'status' in argv)
        identities = [argv for argv in launches[:first_status]
                      if all(flag in argv for flag in
                             ('rev-parse', '--show-toplevel', '--show-object-format', '--verify'))]
        self.assertEqual(len(identities), 1, launches)
        standalone = [argv for argv in launches
                      if 'rev-parse' in argv and '--show-object-format' in argv
                      and '--show-toplevel' not in argv]
        self.assertEqual(standalone, [], launches)

    def test_ready_combines_initial_identity_in_both_git_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm):
                project = self.project(algorithm)
                self.builder.backlog(project)
                head = project.git('rev-parse', 'HEAD')
                result, launches = self.transition(project, 'ready', '--approved-ref', project.ref)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                record = json.loads(result.stdout)
                self.assertEqual(record['task']['status'], 'ready')
                self.assertEqual(record['task']['approved_ref'], project.ref)
                self.assertEqual(project.git('rev-parse', 'HEAD^'), head)
                self.assertEqual(project.git('status', '--porcelain'), '')
                self.assert_identity_read(launches)

    def test_finish_reconciles_before_and_after_the_real_oracles(self):
        project = self.project()
        self.builder.integrated(project)
        head = project.git('rev-parse', 'HEAD')
        tip = project.git('rev-parse', 'task/TASK-001')
        result, launches = self.transition(project, 'finish')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        task = json.loads(result.stdout)['task']
        self.assertEqual(task['status'], 'done')
        self.assertEqual(task['verified_ref'], head)
        evidence = json.loads((project.root / task['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(evidence['branch_tip'], tip)
        self.assertEqual(evidence['tested_commit'], head)
        self.assertEqual(evidence['passed_tests'], 3)
        self.assertEqual(set(evidence['oracle_results']), {fixture.PRIMARY, fixture.SECONDARY})
        # An inventory-specific Git read occurs during the committed journal
        # validation and twice around the real oracle invocation.
        attributes = [argv for argv in launches if 'check-attr' in argv
                      and '--source=' + project.ref in argv]
        self.assertEqual(len(attributes), 3, launches)
        self.assertGreaterEqual(sum('status' in argv for argv in launches), 3)
        self.assertEqual(sum('task/TASK-001^{commit}' in argv for argv in launches), 2)
        self.assert_identity_read(launches)

    def test_finish_rejects_changed_tip_after_a_successful_oracle(self):
        project = self.project(secondary=fixture.SECONDARY_TEST + MOVE_TIP)
        self.builder.integrated(project)
        head = project.git('rev-parse', 'HEAD')
        original_tip = project.git('rev-parse', 'task/TASK-001')
        self.assertNotEqual(original_tip, head)
        node = project.root / 'knowledge/tasks/TASK-001.md'
        original_node = node.read_bytes()
        tree = project.git('write-tree')
        original_evidence = sorted((project.root / 'docs/task-evidence').glob('*.json'))
        result, _ = self.transition(project, 'finish')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('TASK_RACE: implementation tip changed during verification', result.stderr)
        self.assertEqual(project.git('rev-parse', 'task/TASK-001'), head)
        self.assertEqual(project.git('rev-parse', 'HEAD'), head)
        self.assertEqual(project.git('write-tree'), tree)
        self.assertEqual(node.read_bytes(), original_node)
        self.assertEqual(sorted((project.root / 'docs/task-evidence').glob('*.json')),
                         original_evidence)

    def test_ready_rejects_nested_repo_root_without_publishing(self):
        project = self.project()
        self.builder.backlog(project)
        before = project.snapshot()
        result = project.command(
            [sys.executable, 'scripts/tasks.py', '--repo-root', str(project.root / 'src'),
             'ready', 'TASK-001', '--approved-ref', project.ref],
            check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('TASK_MAIN', result.stderr)
        self.assertEqual(project.snapshot(), before)

    def cold_artifacts(self, project, revision, name):
        trace = self.area / (name + '.jsonl')
        result = project.command(
            [sys.executable, '-B', '-c', COLD_ARTIFACTS, revision, str(trace),
             project.contract(1), fixture.PRIMARY, 'src/feature1.py'],
            check=False)
        return result, self.starts(trace)

    def test_cold_finish_artifacts_read_once_and_still_check_target_bytes(self):
        project = self.project()
        self.builder.backlog(project)
        revision = project.git('rev-parse', 'HEAD')
        result, launches = self.cold_artifacts(project, revision, 'cold')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project.write('src/feature1.py', 'def f1(value):\n    return 99\n')
        result, _ = self.cold_artifacts(project, revision, 'dirty')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('TASK_DIRTY: checkout artifact differs from tested commit: src/feature1.py',
                      result.stderr)
        self.assertEqual(len(launches), 1, launches)


if __name__ == '__main__':
    unittest.main()
