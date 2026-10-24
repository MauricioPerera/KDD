"""Count real Git processes while checking immutable snapshots and mutable integrity."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import task_git as journal
from task_model import new_task, render_task
from test_generated_task_evidence import TaskProject


class GitReadBatching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kdd-real-git-batch-')
        self.addCleanup(self.tmp.cleanup)
        self.project = TaskProject(Path(self.tmp.name) / 'project')
        self.root = self.project.root

    def counted(self, operation):
        calls = []
        original = subprocess.Popen

        def start(argv, *args, **kwargs):
            if isinstance(argv, (list, tuple)) and Path(str(argv[0])).stem == 'git':
                calls.append(tuple(str(x) for x in argv))
            return original(argv, *args, **kwargs)

        begin = time.perf_counter()
        with patch.object(subprocess, 'Popen', side_effect=start):
            result = operation()
        return result, calls, time.perf_counter() - begin

    def test_twelve_nodes_use_at_most_five_real_git_processes(self):
        for number in range(1, 13):
            identifier = 'TASK-%03d' % number
            task = new_task(identifier, 'Tarea numero %s \u00f1' % number,
                            'Real object fixture', self.project.contract(1))
            self.project.write('knowledge/tasks/' + identifier + '.md', render_task(task))
        self.project.commit('twelve real task blobs')
        nodes, calls, elapsed = self.counted(lambda: journal.read_nodes(self.root))
        self.assertEqual(set(nodes), {'TASK-%03d' % n for n in range(1, 13)})
        self.assertEqual(nodes['TASK-012'][0]['title'], 'Tarea numero 12 \u00f1')
        self.assertLessEqual(len(calls), 5, 'real Git calls=%s elapsed=%.3f' % (len(calls), elapsed))

    def test_moving_main_between_calls_never_reuses_an_old_snapshot(self):
        self.project.write('knowledge/tasks/TASK-001.md',
                           render_task(new_task('TASK-001', 'Before', 'First title',
                                                self.project.contract(1))))
        old = self.project.commit('first snapshot')
        self.assertEqual(journal.read_nodes(self.root)['TASK-001'][0]['title'], 'Before')
        self.project.write('knowledge/tasks/TASK-001.md',
                           render_task(new_task('TASK-001', 'After', 'Changed title',
                                                self.project.contract(1))))
        self.project.commit('second snapshot')
        self.assertEqual(journal.read_nodes(self.root)['TASK-001'][0]['title'], 'After')
        self.assertEqual(journal.read_nodes(self.root, old)['TASK-001'][0]['title'], 'Before')

    def quality_fixture(self):
        p = self.project
        policy = p.policy()
        policy.pop('generated_task_evidence')
        p.write('src/feature1.py', p.implementation(1))
        for number in range(24):
            name = 'protected/file %s.dat' % number
            p.write(name, 'immutable fixture %s\n' % number)
            policy['protected'].append(name)
        binary = p.root / 'protected/binary.dat'
        binary.write_bytes(b'\x00\xffwith\nbinary\r\ncontent')
        policy['protected'].append('protected/binary.dat')
        p.write('quality/product.json', __import__('json').dumps(policy))
        p.ref = p.commit('synthetic reviewed policy for process measurement')
        spec = importlib.util.spec_from_file_location('quality_batch_candidate',
                                                     ROOT / 'scripts/verify_quality.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return p, module

    def test_quality_twice_uses_at_most_thirty_git_processes(self):
        p, module = self.quality_fixture()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            _, calls, elapsed = self.counted(lambda: module.approve(p.root, 'quality/product.json', p.ref))
        self.assertIn('PASS quality:', output.getvalue())
        self.assertEqual(output.getvalue().count('RUN '), 4)
        self.assertLessEqual(len(calls), 30,
                             'real Git calls=%s elapsed=%.3f' % (len(calls), elapsed))

    def test_index_and_worktree_are_checked_again_after_each_command(self):
        p, module = self.quality_fixture()
        policy = __import__('json').loads((p.root / 'quality/product.json').read_text())
        target = 'protected/file 0.dat'
        policy['checks'][0]['argv'] = [sys.executable, '-c',
            "import subprocess; from pathlib import Path; p=Path(%r); old=p.read_bytes(); "
            "p.write_bytes(b'tampered'); subprocess.run(['git','add',str(p)],check=True); "
            "p.write_bytes(old)" % target]
        p.write('quality/product.json', __import__('json').dumps(policy))
        p.ref = p.commit('simulated command changes index then restores worktree')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(module.Rejected):
            module.approve(p.root, 'quality/product.json', p.ref)
        self.assertNotIn('PASS quality:', output.getvalue())

    def test_missing_protected_git_object_is_never_silently_omitted(self):
        p, module = self.quality_fixture()
        policy = __import__('json').loads((p.root / 'quality/product.json').read_text())
        policy['protected'].append('missing.bin')
        p.write('quality/product.json', __import__('json').dumps(policy))
        p.ref = p.commit('malformed reviewed fixture with missing protected blob')
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(module.Rejected):
            module.approve(p.root, 'quality/product.json', p.ref)


if __name__ == '__main__':
    unittest.main()
