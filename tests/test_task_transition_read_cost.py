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



CHANGE_TARGET = '''
    def test_changes_checkout_target(self):
        from pathlib import Path

        target = Path('src/feature1.py')
        target.write_bytes(target.read_bytes() + b'\\n# Oracle side effect\\n')
'''

STATUS_RACE = '''
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
sys.path.insert(0, str(root / 'scripts'))
import task_git as journal
from task_model import TaskError

approved, other_head = sys.argv[1:]
original_output = journal._output
moved = False

def after_initial_read(repo, args):
    global moved
    if not moved and args[0] == 'status':
        subprocess.run(['git', '-C', str(repo), 'reset', '--hard', other_head],
                       check=True, capture_output=True, timeout=20)
        moved = True
    return original_output(repo, args)

journal._output = after_initial_read
try:
    journal.mutate(root, 'ready', 'TASK-001', {'approved_ref': approved})
except TaskError as error:
    print(error, file=sys.stderr)
    sys.exit(1)
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
        first_inventory = next(i for i, argv in enumerate(launches)
                               if 'ls-tree' in argv and 'knowledge/tasks' in argv)
        initial = launches[:first_inventory]
        first_status = next(i for i, argv in enumerate(initial) if 'status' in argv)
        self.assertLessEqual(len(initial), 3, initial)
        identities = [argv for argv in initial[:first_status]
                      if all(flag in argv for flag in
                             ('rev-parse', '--show-toplevel', '--show-object-format', '--verify'))]
        self.assertEqual(len(identities), 1, initial)
        self.assertEqual(identities[0][-1], 'HEAD^{commit}')
        self.assertEqual(sum('--show-toplevel' in argv for argv in initial), 1, initial)

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

    def test_finish_rechecks_target_after_the_oracle_even_when_status_is_clean(self):
        project = self.project(secondary=fixture.SECONDARY_TEST + CHANGE_TARGET)
        self.builder.integrated(project)
        target = 'src/feature1.py'
        project.git('update-index', '--assume-unchanged', target)
        before = project.snapshot()
        path = project.root / target
        original = path.read_bytes()
        evidence = project.root / 'docs/task-evidence'
        receipts = sorted(evidence.glob('*.json'))
        result, _ = self.transition(project, 'finish')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('TASK_DIRTY: checkout artifact differs from tested commit: ' + target,
                      result.stderr)
        self.assertEqual(path.read_bytes(), original + b'\n# Oracle side effect\n')
        self.assertEqual(project.snapshot(), before)
        self.assertEqual(sorted(evidence.glob('*.json')), receipts)

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

    def test_ready_does_not_reuse_initial_head_after_status_observes_another(self):
        project = self.project()
        self.builder.backlog(project)
        initial = project.git('rev-parse', 'HEAD')
        path = project.root / fixture.BINARY
        path.write_bytes(b'left\nright\n')
        other = project.commit('Change the approved binary fixture in the alternate revision')
        project.git('reset', '--hard', initial)
        node = project.root / 'knowledge/tasks/TASK-001.md'
        original_node = node.read_bytes()
        result = project.command(
            [sys.executable, '-B', '-c', STATUS_RACE, project.ref, other], check=False)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stderr, r'TASK_(?:RACE|APPROVAL):')
        self.assertEqual(project.git('rev-parse', 'HEAD'), other)
        self.assertEqual(node.read_bytes(), original_node)
        self.assertEqual(path.read_bytes(), b'left\nright\n')
        self.assertEqual(project.git('status', '--porcelain'), '')

    def cold_artifacts(self, project, revision, name):
        trace = self.area / (name + '.jsonl')
        result = project.command(
            [sys.executable, '-B', '-c', COLD_ARTIFACTS, revision, str(trace),
             project.contract(1), fixture.PRIMARY, 'src/feature1.py'],
            check=False)
        return result, self.starts(trace)

    def test_cold_finish_artifacts_read_once_and_check_all_four_paths(self):
        project = self.project()
        self.builder.backlog(project)
        revision = project.git('rev-parse', 'HEAD')
        result, launches = self.cold_artifacts(project, revision, 'cold')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        paths = (project.contract(1), 'knowledge/tasks/TASK-001.md',
                 fixture.PRIMARY, 'src/feature1.py')
        for index, name in enumerate(paths):
            with self.subTest(path=name):
                path = project.root / name
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b'\n# Checkout drift\n')
                    result, _ = self.cold_artifacts(project, revision, f'dirty-{index}')
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn('TASK_DIRTY: checkout artifact differs from tested commit: ' + name,
                                  result.stderr)
                finally:
                    path.write_bytes(original)
        self.assertEqual(len(launches), 1, launches)

    def test_cold_finish_rejects_missing_blobs_and_keeps_first_error(self):
        project = self.project()
        self.builder.backlog(project)
        target = 'src/feature1.py'
        project.git('rm', '--cached', target)
        project.git('commit', '-qm', 'Prepare a revision without the target blob')
        revision = project.git('rev-parse', 'HEAD')
        self.assertTrue((project.root / target).is_file())
        result, _ = self.cold_artifacts(project, revision, 'missing')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('TASK_GIT: missing or invalid blob: ' + target, result.stderr)
        project.write(project.contract(1), '# Earlier checkout drift\n')
        result, _ = self.cold_artifacts(project, revision, 'earlier-drift')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('TASK_DIRTY: checkout artifact differs from tested commit: ' +
                      project.contract(1), result.stderr)


if __name__ == '__main__':
    unittest.main()
