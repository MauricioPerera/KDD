"""Real Board, coordinator and Git tests for one-snapshot task detail."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tests.test_generated_task_evidence import TaskProject

ROOT = Path(__file__).resolve().parents[1]
NODE = 'knowledge/tasks/TASK-001.md'
BOARD = (ROOT / 'tools/kdd-board/src/git-task-store.ts').as_uri()


BOARD_CLIENT = r"""
import processTools from 'node:child_process';
import {appendFileSync} from 'node:fs';
import {syncBuiltinESMExports} from 'node:module';
import {promisify} from 'node:util';

const optionsTrace = process.env.KDD_FIXTURE_BOARD_OPTIONS;
if (optionsTrace) {
  const original = processTools.execFile;
  const run = promisify(original);
  const observer = (...args) => original(...args);
  observer[promisify.custom] = (binary, args, options) => {
    const evidence = [binary === 'git' ? 'git' : args[3], options.timeout, options.maxBuffer];
    appendFileSync(optionsTrace, JSON.stringify(evidence) + '\n');
    return run(binary, args, options);
  };
  processTools.execFile = observer;
  syncBuiltinESMExports();
}
const {GitTaskStore} = await import(process.argv[1]);
const store = new GitTaskStore(process.argv[2]);
try {
  const result = process.argv[3] === 'get'
    ? await store.get(process.argv[5])
    : await store.transition(process.argv[5], JSON.parse(process.argv[4]));
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

    real_run = subprocess.run

    def trace_batches(*args, **kwargs):
        argv = args[0] if args else kwargs.get('args', ())
        payload = kwargs.get('input')
        if isinstance(argv, (list, tuple)) and 'cat-file' in argv and payload:
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            count = sum(row.endswith(b':knowledge/tasks/TASK-001.md')
                        for row in payload.splitlines())
            if count:
                with Path(os.environ['KDD_FIXTURE_BATCH_SIZES']).open('a', encoding='utf-8') as stream:
                    stream.write(str(count) + '\n')
        return real_run(*args, **kwargs)

    subprocess.run = trace_batches
"""

PIN_PROBE = r"""
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
sys.path.insert(0, str(root / 'scripts'))
import tasks

previous, advanced, boundary = sys.argv[1:]
actual = subprocess.run
moved = False
resolutions = 0

def move_main():
    global moved
    actual(['git', 'update-ref', 'refs/heads/main', advanced, previous],
           cwd=root, check=True, capture_output=True, timeout=20)
    moved = True

def observe_git(*args, **kwargs):
    global resolutions
    argv = args[0] if args else kwargs.get('args', ())
    inventory = ('ls-tree' in argv and 'knowledge/tasks' in argv)
    history = ('log' in argv or 'rev-list' in argv) and 'knowledge/tasks/TASK-001.md' in argv
    resolve_main = 'rev-parse' in argv and any(
        revision in argv for revision in ('main^{commit}', 'refs/heads/main^{commit}'))
    if not moved and ((boundary == 'inventory' and inventory) or (boundary == 'history' and history)):
        move_main()
    result = actual(*args, **kwargs)
    if resolve_main:
        resolutions += 1
        if not moved and boundary == 'resolution' and result.returncode == 0:
            move_main()
    return result

subprocess.run = observe_git
code = tasks.main(['snapshot', 'TASK-001', '--json'])
if code == 0:
    assert moved, 'the probe must exercise the Git boundary'
    assert resolutions == 1, f'main was resolved {resolutions} times'
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
        self.batches = self.area / 'batch-sizes.log'
        (self.instrument / 'sitecustomize.py').write_text(COORDINATOR_TRACE, encoding='utf-8')
        self.p.act('create', 1, '--title', 'Own task for the Board',
                   '--description', 'Read one committed journal', '--contract', self.p.contract(1))

    def board(self, operation, data=None, move=None, task_id='TASK-001'):
        python_trace = self.area / 'coordinators.log'
        git_trace = self.area / 'git-trace.jsonl'
        env = dict(self.p.env, KDD_PYTHON=sys.executable, PYTHONPATH=str(self.instrument),
                   KDD_FIXTURE_COORDINATORS=str(python_trace),
                   KDD_FIXTURE_BATCH_SIZES=str(self.batches),
                   GIT_TRACE2_EVENT=str(git_trace))
        if move is not None:
            env.update(KDD_FIXTURE_MAIN_BEFORE=move[0], KDD_FIXTURE_MAIN_AFTER=move[1])
        if (self.area / 'options.log').exists():
            env['KDD_FIXTURE_BOARD_OPTIONS'] = str(self.area / 'options.log')
        result = self.p.command(['node', '--input-type=module', '-e', BOARD_CLIENT,
                                 BOARD, str(self.p.root), operation, json.dumps(data), task_id],
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
        delivered = self.p.git('rev-parse', 'main')
        self.p.git('branch', 'delivery', delivered)
        self.p.git('switch', '-q', '--detach', self.p.ref)
        self.p.git('branch', '-f', 'main', self.p.ref)
        self.p.git('switch', '-q', 'main')
        self.p.git('merge', '--no-ff', '-qm', 'Import the original journal', 'delivery')
        self.assertEqual(self.p.git('rev-parse', 'main^2'), delivered)
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

    def append_task_history(self, count):
        # Populate a real, longer Git history with one setup process.
        base = self.p.git('rev-parse', 'main')
        original = (self.p.root / NODE).read_bytes()
        stream = bytearray()
        for index in range(count):
            stream.extend(b'commit refs/heads/main\n')
            stream.extend(f'committer Fixture <fixture@example.invalid> {1700000000 + index} +0000\n'.encode())
            stream.extend(b'data 7\nfixture\n')
            if index == 0:
                stream.extend(f'from {base}\n'.encode())
            version = original + f'\nRecord {index}\n'.encode()
            stream.extend(f'M 100644 inline {NODE}\ndata {len(version)}\n'.encode())
            stream.extend(version + b'\n\n')
        result = subprocess.run(['git', 'fast-import', '--quiet'], cwd=self.p.root,
                                env=self.p.env, input=bytes(stream), timeout=45,
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))

    def test_long_detail_keeps_all_versions_and_bounds_requests_per_batch(self):
        self.append_task_history(34)
        expected = self.p.act('history', 1)
        self.assertEqual(len(expected), 35)
        before = self.p.snapshot()
        result, value, _, launches = self.board('get')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(value['journal'], expected)
        self.assertEqual(self.p.snapshot(), before)
        batches = ([int(line) for line in self.batches.read_text(encoding='utf-8').splitlines()]
                   if self.batches.exists() else [])
        self.assertTrue(batches)
        self.assertLessEqual(max(batches), 32, batches)
        self.assertGreaterEqual(sum(batches), 34)
        self.assertLessEqual(launches, 9)

    def test_combined_output_preserves_large_details_from_separate_reads(self):
        path = self.p.root / NODE
        reason = 'x' * (4 * 1024 * 1024 + 32)
        source = path.read_text(encoding='utf-8')
        updated, changes = re.subn(r'^reason: [^\n]*$', "reason: '" + reason + "'", source,
                                   count=1, flags=re.MULTILINE)
        self.assertEqual(changes, 1)
        self.p.write(NODE, updated)
        tip = self.p.commit('Record a long task reason')
        options = self.area / 'options.log'
        options.touch()
        result, value, commands, _ = self.board('get')
        self.assertEqual(result.returncode, 0, result.stderr or str(result.returncode))
        self.assertGreater(len(result.stdout.encode('utf-8')), 8 * 1024 * 1024)
        self.assertTrue(value['reason'] == reason)
        self.assertEqual(value['journal'][-1]['commit'], tip)
        self.assertTrue(value['journal'][-1]['reason'] == reason)
        self.assertEqual(commands, ['snapshot'])
        mib = 1024 * 1024
        self.assertEqual([json.loads(line) for line in options.read_text(encoding='utf-8').splitlines()],
                         [['git', 180_000, 8 * mib], ['snapshot', 360_000, 16 * mib],
                          ['git', 180_000, 8 * mib]])

    def test_ready_uses_one_read_and_the_real_mutation(self):
        before = self.p.git('rev-parse', 'HEAD')
        options = self.area / 'options.log'
        options.touch()
        result, value, commands, _ = self.board('ready', {'status': 'ready', 'approved_ref': self.p.ref})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(value['task']['status'], 'ready')
        self.assertEqual(value['task']['approved_ref'], self.p.ref)
        self.assertEqual(value['commit'], self.p.git('rev-parse', 'HEAD'))
        self.assertEqual(self.p.git('rev-parse', 'HEAD^'), before)
        self.assertEqual(self.p.git('status', '--porcelain'), '')
        self.assertEqual(commands, ['snapshot', 'ready'])
        self.assertEqual(json.loads(options.read_text(encoding='utf-8').splitlines()[-1]),
                         ['ready', 180_000, 8 * 1024 * 1024])

    def test_detail_rejects_a_corrupt_unrelated_node_in_the_current_snapshot(self):
        self.p.write('knowledge/tasks/TASK-002.md', 'Missing Task metadata\n')
        self.p.commit('Malformed separate task')
        before = self.p.snapshot()
        result, value, _, _ = self.board('get', task_id='TASK-999')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(value, {'code': 'TASK_UNAVAILABLE', 'status': 503})
        self.assertEqual(self.p.snapshot(), before)

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

    def test_detail_reports_missing_task_at_tip(self):
        self.p.git('rm', '--', NODE)
        self.p.commit('Remove the task from current main')
        before = self.p.snapshot()
        result, value, _, _ = self.board('get')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(value, {'code': 'TASK_MISSING', 'status': 404})
        self.assertEqual(self.p.snapshot(), before)

    def test_detail_rejects_a_deleted_historical_blob_after_restoration(self):
        path = self.p.root / NODE
        normal = path.read_bytes()
        self.p.git('rm', '--', NODE)
        self.p.commit('Remove the intermediate task')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(normal)
        self.p.commit('Restore the task')
        before = self.p.snapshot()
        result, value, _, _ = self.board('get')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(value, {'code': 'TASK_GIT', 'status': 409})
        self.assertEqual(self.p.snapshot(), before)

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

    def test_cli_reads_the_initial_commit_when_main_moves(self):
        previous, advanced = self.alternative()
        for boundary in ('resolution', 'inventory', 'history'):
            with self.subTest(boundary=boundary):
                self.p.git('reset', '--hard', previous)
                result = self.p.command([sys.executable, '-B', '-c', PIN_PROBE, previous,
                                         advanced, boundary], check=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['task']['status'], 'backlog')
                self.assertEqual([item['commit'] for item in value['journal']], [previous])
                self.assertEqual(self.p.git('rev-parse', 'main'), advanced)


if __name__ == '__main__':
    unittest.main()
