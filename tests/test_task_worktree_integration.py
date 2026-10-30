"""Concurrent real workers, shared locks, merge recovery and a protected bare remote.

The hook is a local simulation, not a claim about GitHub branch protection.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_generated_task_evidence import TaskProject


class TaskWorktreeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_tmp = tempfile.TemporaryDirectory(prefix='kdd-worktree-base-')
        cls.addClassCleanup(cls.base_tmp.cleanup)
        cls.base_project = TaskProject(Path(cls.base_tmp.name) / 'base', count=3)
        cls.base_project.complete(1)
        for number in (2, 3):
            cls.base_project.create(number, (1,))
            cls.base_project.act('start', number, '--assignee', 'worker%s' % number)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kdd-worktree-regression-')
        self.addCleanup(self.tmp.cleanup)
        self.area = Path(self.tmp.name)
        target = self.area / 'coordinator'
        self.base_project.command(['git', 'clone', '-q', '--shared',
                                   str(self.base_project.root), str(target)])
        self.project = TaskProject(target, count=3, initialize=False)
        self.project.ref = self.base_project.ref
        for name, value in [('user.name', 'Fixture worker'),
                            ('user.email', 'fixture@example.invalid'),
                            ('core.autocrlf', 'false'), ('commit.gpgsign', 'false')]:
            self.project.git('config', name, value)
        for number in (2, 3):
            self.project.git('branch', 'task/TASK-%03d' % number,
                             'origin/task/TASK-%03d' % number)
        self.worktrees = {}
        for number in (2, 3):
            target = self.area / ('worker%s' % number)
            self.project.git('worktree', 'add', '-q', str(target), 'task/TASK-%03d' % number)
            self.worktrees[number] = target

    def process(self, argv, cwd):
        child = subprocess.Popen(argv, cwd=cwd, env=self.project.env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.addCleanup(lambda: self.stop(child))
        return child

    @staticmethod
    def stop(child):
        if child.poll() is None:
            child.terminate()
        child.communicate(timeout=15)

    def wait_for(self, predicate, children=(), timeout=30):
        until = time.monotonic() + timeout
        while not predicate():
            self.assertTrue(all(p.poll() is None for p in children),
                            'a worker failed before reaching its barrier')
            self.assertLess(time.monotonic(), until, 'worker barrier timed out')
            time.sleep(0.02)

    def test_two_live_workers_commit_and_integrate_preserving_both_tips(self):
        release = self.area / 'release'
        workers = []
        for number in (2, 3):
            ready = self.area / ('ready%s' % number)
            script = self.area / ('run-worker%s.py' % number)
            script.write_text("""from pathlib import Path
import subprocess,time
ready,release=Path(%r),Path(%r)
ready.write_text('ready')
limit=time.monotonic()+30
while not release.exists():
    if time.monotonic()>limit: raise RuntimeError('barrier timeout')
    time.sleep(0.02)
Path('src/feature%s.py').write_text(%r,encoding='utf-8')
subprocess.run(['git','add','src/feature%s.py'],check=True)
subprocess.run(['git','commit','-qm','real concurrent implementation'],check=True)
""" % (str(ready), str(release), number, self.project.implementation(number), number),
                              encoding='utf-8')
            workers.append(self.process([sys.executable, str(script)], self.worktrees[number]))
        self.wait_for(lambda: all((self.area / ('ready%s' % n)).exists() for n in (2, 3)), workers)
        self.assertTrue(all(p.poll() is None for p in workers))
        release.write_text('both workers are alive; release')
        for child in workers:
            out, err = child.communicate(timeout=60)
            self.assertEqual(child.returncode, 0, out + err)
        p = self.project
        tips = {n:p.git('rev-parse', 'task/TASK-%03d' % n) for n in (2, 3)}
        for number in (2, 3):
            p.git('merge', '--no-ff', 'task/TASK-%03d' % number, '-qm', 'preserve concurrent implementation')
            done = p.act('finish', number)
            self.assertEqual(done['task']['status'], 'done')
            p.git('merge-base', '--is-ancestor', tips[number], 'main')
            self.assertEqual(p.git('rev-parse', 'task/TASK-%03d' % number), tips[number])
        result = p.command([sys.executable, 'scripts/validate_tasks.py', '--base-ref', p.ref,
                            '--head-ref', 'main'])
        self.assertIn('0 error(s)', result.stdout)
        self.assertEqual(p.git('status', '--porcelain'), '')

    def test_real_conflict_and_abort_preserve_both_worker_tips_and_main(self):
        p = self.project
        for number in (2, 3):
            root = self.worktrees[number]
            (root / 'integration.txt').write_text('worker%s\n' % number)
            p.command(['git', '-C', str(root), 'add', 'integration.txt'])
            p.command(['git', '-C', str(root), 'commit', '-qm', 'conflicting integration fixture'])
        tips = [p.git('rev-parse', 'task/TASK-%03d' % n) for n in (2, 3)]
        p.git('merge', '--no-ff', 'task/TASK-002', '-qm', 'first integration')
        before = p.snapshot()
        result = p.command(['git', 'merge', '--no-ff', 'task/TASK-003', '-m',
                            'conflicting integration'], check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(p.git('diff', '--name-only', '--diff-filter=U'))
        p.git('merge', '--abort')
        self.assertEqual(p.snapshot(), before)
        self.assertEqual([p.git('rev-parse', 'task/TASK-%03d' % n) for n in (2, 3)], tips)
        for number in (2, 3):
            self.assertEqual((self.worktrees[number] / 'integration.txt').read_text(),
                             'worker%s\n' % number)

    def test_interrupted_coordinator_leaves_shared_lock_until_explicit_recovery(self):
        p = self.project
        ready = self.area / 'lock-ready'
        script = self.area / 'lock-owner.py'
        script.write_text("""import sys,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'scripts'))
from task_git import _lock
with _lock(Path.cwd()):
    Path(%r).write_text('locked')
    while True: time.sleep(1)
""" % str(ready), encoding='utf-8')
        owner = self.process([sys.executable, str(script)], p.root)
        self.wait_for(ready.exists, (owner,))
        common = Path(p.git('rev-parse', '--git-common-dir'))
        lock = (p.root / common).resolve() / 'kdd-tasks.lock'
        self.assertEqual(lock.read_text(), str(owner.pid))
        before = p.snapshot()
        for root in (p.root, self.worktrees[2]):
            result = p.command([sys.executable, str(p.root / 'scripts/tasks.py'),
                                '--repo-root', str(root), 'block', 'TASK-002',
                                '--reason', 'probe lock'], cwd=root, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('TASK_LOCK', result.stderr)
        owner.terminate()
        owner.communicate(timeout=15)
        self.assertTrue(lock.exists(), 'interrupted owner must not imply automatic lock deletion')
        result = p.act('block', 2, '--reason', 'probe stale lock', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('TASK_LOCK', result.stderr)
        self.assertEqual(p.snapshot(), before)
        # Explicit recovery is safe here only because this fixture owns the terminated PID.
        self.assertEqual(lock.read_text(), str(owner.pid))
        self.assertTrue(lock.resolve().is_relative_to(self.area.resolve()))
        lock.unlink()
        result = p.act('block', 2, '--reason', 'explicit fixture recovery')
        self.assertEqual(result['task']['status'], 'needs_human_input')

    def test_bare_remote_rejects_direct_main_and_accepts_valid_review_branch_only(self):
        p = self.project
        remote = self.area / 'protected.git'
        p.command(['git', 'init', '--bare', '-q', str(remote)])
        p.git('remote', 'set-url', 'origin', str(remote))
        p.git('push', '-q', 'origin', 'main')
        base = p.git('rev-parse', 'HEAD')
        hook = remote / 'hooks/pre-receive'
        python = sys.executable.replace('\\', '/')
        validator = str(ROOT / 'scripts/validate_tasks.py').replace('\\', '/')
        hook.write_text("""#!/bin/sh
while read old new ref
do
  if [ "$ref" = refs/heads/main ]; then
    echo 'MAIN_PROTECTED: publish a review branch' >&2
    exit 1
  fi
  '%s' '%s' --repo-root "$PWD" --base-ref '%s' --head-ref "$new" || exit 1
done
""" % (python, validator, base), encoding='utf-8', newline='\n')
        hook.chmod(0o700)
        p.act('block', 2, '--reason', 'review branch fixture')
        tip = p.git('rev-parse', 'HEAD')
        rejected = p.command(['git', 'push', 'origin', 'main'], check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('MAIN_PROTECTED', rejected.stderr)
        p.git('push', '-q', 'origin', 'main:refs/heads/codex/review-state')
        self.assertEqual(p.git('ls-remote', '--heads', 'origin', 'main').split()[0], base)
        self.assertEqual(p.git('ls-remote', '--heads', 'origin', 'codex/review-state').split()[0], tip)
        node = p.root / 'knowledge/tasks/TASK-002.md'
        p.write('knowledge/tasks/TASK-002.md',
                node.read_text().replace("status: 'needs_human_input'", "status: 'done'"))
        p.commit('invalid review history fixture')
        invalid = p.command(['git', 'push', 'origin', 'main:refs/heads/codex/review-state'], check=False)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn('TASK_', invalid.stderr + invalid.stdout)
        self.assertEqual(p.git('ls-remote', '--heads', 'origin', 'codex/review-state').split()[0], tip)
        self.assertEqual(p.git('ls-remote', '--heads', 'origin', 'main').split()[0], base)


if __name__ == '__main__':
    unittest.main()
