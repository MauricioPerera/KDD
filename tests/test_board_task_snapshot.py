"""Real Board, coordinator and Git tests for one-snapshot task detail."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_generated_task_evidence import TaskProject

ROOT = Path(__file__).resolve().parents[1]
NODE = 'knowledge/tasks/TASK-001.md'
BOARD = (ROOT / 'tools/kdd-board/src/git-task-store.ts').as_uri()


BOARD_CLIENT = r"""
const {GitTaskStore} = await import(process.argv[1]);
const store = new GitTaskStore(process.argv[2]);
try {
  const result = process.argv[3] === 'get'
    ? await store.get('TASK-001')
    : await store.transition('TASK-001', JSON.parse(process.argv[4]));
  console.log(JSON.stringify(result));
} catch (error) {
  console.log(JSON.stringify({code:error.code, status:error.status}));
  process.exitCode = 2;
}
"""

COORDINATOR_TRACE = r"""
import os
from pathlib import Path
import subprocess
import sys

if len(sys.argv) > 4 and Path(sys.argv[0]).name == 'tasks.py':
    operation = sys.argv[3]
    trace = Path(os.environ['KDD_FIXTURE_COORDINATORS'])
    with trace.open('a', encoding='utf-8') as stream:
        stream.write(operation + '\n')
    previous = os.environ.get('KDD_FIXTURE_MAIN_BEFORE')
    advanced = os.environ.get('KDD_FIXTURE_MAIN_AFTER')
    once = trace.with_suffix('.moved')
    if advanced and operation in ('show', 'snapshot') and not once.exists():
        result = subprocess.run(['git', 'update-ref', 'refs/heads/main', advanced, previous],
                                capture_output=True, timeout=20)
        if result.returncode:
            os._exit(87)
        once.write_text(advanced, encoding='ascii')
"""

PIN_PROBE = r"""
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
sys.path.insert(0, str(root / 'scripts'))
import tasks
import task_git

previous, advanced = sys.argv[1:]
actual = task_git.git
moved = False

def move_before_history(project, *args):
    global moved
    if args[0] == 'log' and not moved:
        subprocess.run(['git', 'update-ref', 'refs/heads/main', advanced, previous],
                       cwd=root, check=True, capture_output=True, timeout=20)
        moved = True
    return actual(project, *args)

task_git.git = move_before_history
code = tasks.main(['snapshot', 'TASK-001', '--json'])
if code == 0:
    assert moved, 'the probe must exercise a real history read'
sys.exit(code)
"""


class BoardTaskSnapshot(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='kdd-board-snapshot-')
        self.addCleanup(scratch.cleanup)
        self.area = Path(scratch.name)
        self.p = TaskProject(self.area / 'product')
        self.instrument = self.area / 'instrument'
        self.instrument.mkdir()
        (self.instrument / 'sitecustomize.py').write_text(COORDINATOR_TRACE, encoding='utf-8')
        self.p.act('create', 1, '--title', 'Own task for the Board',
                   '--description', 'Read one committed journal', '--contract', self.p.contract(1))

    def board(self, operation, data=None, move=None):
        python_trace = self.area / 'coordinators.log'
        git_trace = self.area / 'git-trace.jsonl'
        env = dict(self.p.env, KDD_PYTHON=sys.executable, PYTHONPATH=str(self.instrument),
                   KDD_FIXTURE_COORDINATORS=str(python_trace), GIT_TRACE2_EVENT=str(git_trace))
        if move is not None:
            env.update(KDD_FIXTURE_MAIN_BEFORE=move[0], KDD_FIXTURE_MAIN_AFTER=move[1])
        result = self.p.command(['node', '--input-type=module', '-e', BOARD_CLIENT,
                                 BOARD, str(self.p.root), operation, json.dumps(data)],
                                check=False, env=env)
        try:
            value = json.loads(result.stdout)
        except ValueError:
            self.fail(result.stdout + result.stderr)
        commands = python_trace.read_text(encoding='utf-8').splitlines()
        starts = sum(json.loads(line)['event'] == 'start'
                     for line in git_trace.read_text(encoding='utf-8').splitlines())
        return result, value, commands, starts

    def ready(self):
        return self.p.act('ready', 1, '--approved-ref', self.p.ref)

    def alternative(self):
        previous = self.p.git('rev-parse', 'HEAD')
        advanced = self.ready()['commit']
        self.p.git('reset', '--hard', previous)
        return previous, advanced

    def test_get_uses_one_coordinator_and_bounds_git_for_seven_commits(self):
        self.ready()
        self.p.act('start', 1, '--assignee', 'fixture')
        self.p.act('block', 1, '--reason', 'Waiting')
        self.p.act('resume', 1, '--reason', 'Review provided')
        self.p.act('start', 1, '--assignee', 'fixture')
        self.p.implement(1)
        self.p.act('finish', 1)
        expected = self.p.act('show', 1)
        journal = self.p.act('history', 1)
        self.assertEqual(len(journal), 7)
        self.p.git('switch', '-q', '--detach', self.p.ref)
        before = self.p.snapshot()
        result, value, commands, launches = self.board('get')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(value['sourceRef'], 'main')
        self.assertEqual(value['id'], 'TASK-001')
        self.assertEqual({key: value[key] for key in expected}, expected)
        self.assertEqual(value['journal'], journal)
        self.assertEqual(self.p.snapshot(), before)
        with self.subTest(metric='Python'):
            self.assertEqual(commands, ['snapshot'])
        with self.subTest(metric='Git'):
            self.assertGreater(launches, 0)
            self.assertLessEqual(launches, 8)

    def test_ready_uses_one_read_and_the_real_mutation(self):
        before = self.p.git('rev-parse', 'HEAD')
        result, value, commands, _ = self.board('ready', {'status': 'ready', 'approved_ref': self.p.ref})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(value['task']['status'], 'ready')
        self.assertEqual(value['task']['approved_ref'], self.p.ref)
        self.assertEqual(value['commit'], self.p.git('rev-parse', 'HEAD'))
        self.assertEqual(self.p.git('rev-parse', 'HEAD^'), before)
        self.assertEqual(self.p.git('status', '--porcelain'), '')
        self.assertEqual(commands, ['snapshot', 'ready'])

    def test_ready_rejects_a_corrupt_intermediate_node_after_restoration(self):
        path = self.p.root / NODE
        good = path.read_bytes()
        self.p.write(NODE, 'Missing Task metadata\n')
        self.p.commit('Malformed intermediate record')
        path.write_bytes(good)
        self.p.commit('Restore the valid current task')
        before = self.p.snapshot()
        result, value, commands, _ = self.board('ready', {'status': 'ready', 'approved_ref': self.p.ref})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(value, {'code': 'TASK_UNAVAILABLE', 'status': 503})
        self.assertEqual(self.p.snapshot(), before)
        self.assertEqual(path.read_bytes(), good)
        self.assertNotIn('ready', commands)

    def test_board_retries_a_read_when_main_moves(self):
        versions = self.alternative()
        checkout = (self.p.root / NODE).read_bytes()
        result, value, commands, _ = self.board('get', move=versions)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(value['status'], 'ready')
        self.assertEqual(value['journal'][-1]['commit'], versions[1])
        self.assertEqual(self.p.git('rev-parse', 'main'), versions[1])
        self.assertEqual((self.p.root / NODE).read_bytes(), checkout)
        self.assertEqual(commands, ['snapshot', 'snapshot'])

    def test_cli_reads_the_initial_commit_when_main_moves_before_history(self):
        previous, advanced = self.alternative()
        result = self.p.command([sys.executable, '-B', '-c', PIN_PROBE, previous, advanced],
                                check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['task']['status'], 'backlog')
        self.assertEqual([item['commit'] for item in value['journal']], [previous])
        self.assertEqual(self.p.git('rev-parse', 'main'), advanced)


if __name__ == '__main__':
    unittest.main()
