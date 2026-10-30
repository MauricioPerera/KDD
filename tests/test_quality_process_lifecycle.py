"""Real approved quality commands, owned processes and immutable helper origin."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/verify_quality.py'
WORKER = '''from pathlib import Path
import os,subprocess,sys,time
root=Path(__file__).resolve().parent
state=root/'.audit'
if '--spawn' in sys.argv:
    child=subprocess.Popen([sys.executable,__file__],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    until=time.monotonic()+8
    while not (state/('ready-'+str(child.pid))).exists() and time.monotonic()<until:
        time.sleep(.01)
    assert (state/('ready-'+str(child.pid))).exists(),'grandchild readiness failed'
(state/('ready-'+str(os.getpid()))).write_text('ready')
until=time.monotonic()+20
while not (state/'release').exists() and time.monotonic()<until:
    time.sleep(.01)
if (state/'release').exists():
    if '--neighbor' not in sys.argv:
        (root/'oracle.py').write_text('assert False\\n',encoding='utf-8')
    (state/('done-'+str(os.getpid()))).write_text('done')
'''
LAUNCHER = '''from pathlib import Path
import subprocess,sys,time
root=Path(__file__).resolve().parent
argv=[sys.executable,str(root/'worker.py')]
if '--grandchild' in sys.argv:argv.append('--spawn')
child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
ready=root/'.audit'/('ready-'+str(child.pid))
until=time.monotonic()+10
while not ready.exists() and time.monotonic()<until:time.sleep(.01)
assert ready.exists(),'child readiness failed'
if '--timeout' in sys.argv:time.sleep(30)
if '--fail' in sys.argv:raise SystemExit(7)
'''


def alive(pid):
    if os.name == 'nt':
        from ctypes import wintypes as w
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        kernel.WaitForSingleObject.restype = w.DWORD
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.CloseHandle.restype = w.BOOL
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return False
            raise ctypes.WinError(error)
        try:
            status = kernel.WaitForSingleObject(handle, 0)
            if status not in (0, 258):
                raise ctypes.WinError(ctypes.get_last_error())
            return status == 258
        finally:
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
    try:
        os.kill(pid, 0)
        stat = Path('/proc') / str(pid) / 'stat'
        return not stat.exists() or stat.read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except ProcessLookupError:
        return False


class QualityProcessLifecycle(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-quality-owned-')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name) / 'product space-\u00f1'
        self.root.mkdir()
        self.state = self.root / '.audit'
        self.state.mkdir()
        self.addCleanup(self.release_children)
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
            GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME='Synthetic reviewer', GIT_AUTHOR_EMAIL='fixture@example.invalid',
            GIT_COMMITTER_NAME='Synthetic reviewer', GIT_COMMITTER_EMAIL='fixture@example.invalid')
        for key in ('PYTHONPATH', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
            self.env.pop(key, None)
        self.git('init', '-q', '-b', 'main')
        for key, value in [('core.autocrlf', 'false'), ('core.symlinks', 'false'),
                           ('gc.autoDetach', 'false'), ('maintenance.autoDetach', 'false')]:
            self.git('config', key, value)
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/process_tree.py', self.root / 'scripts/process_tree.py')
        shutil.copyfile(SCRIPT, self.root / 'scripts/verify_quality.py')
        self.write('.gitignore', '.audit/\n__pycache__/\n')
        self.write('worker.py', WORKER)
        self.write('launcher.py', LAUNCHER)
        self.write('oracle.py', 'assert True\n')
        self.policy = dict(protected=['oracle.py', 'worker.py', 'launcher.py'],
            implementation=['scripts/process_tree.py'], pm=[],
            required_kinds=['functional', 'adversarial'], checks=[
                dict(name='owned', kind='functional', argv=[sys.executable, 'launcher.py'], timeout=15),
                dict(name='rounds', kind='adversarial', argv=[sys.executable, '-c',
                    "from pathlib import Path; p=Path('.audit/rounds'); p.write_text(p.read_text()+'x' if p.exists() else 'x')"], timeout=10)])
        self.freeze()

    def write(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8', newline='\n')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], env=self.env,
            stderr=subprocess.PIPE, timeout=30).decode('utf-8').strip()

    def freeze(self):
        self.write('quality.json', json.dumps(self.policy))
        self.git('add', '-A')
        self.git('commit', '-qm', 'Synthetic quality fixture, not a project approval')
        self.ref = self.git('rev-parse', 'HEAD')

    def release_children(self):
        if self.state.exists():
            (self.state / 'release').write_text('release', encoding='utf-8')
            until = time.monotonic() + 3
            pids = [int(p.name.split('-')[1]) for p in self.state.glob('ready-*')]
            while any(alive(pid) for pid in pids) and time.monotonic() < until:
                time.sleep(.02)

    def invoke(self, runner=SCRIPT):
        return subprocess.run([sys.executable, str(runner), '--repo-root', str(self.root),
            '--policy', 'quality.json', '--approved-ref', self.ref], env=self.env,
            capture_output=True, text=True, encoding='utf-8', timeout=40)

    def assert_contained(self, result, success=True, children=2, exclude=()):
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS quality:', result.stdout)
            self.assertEqual((self.state / 'rounds').read_text(), 'xx')
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('PASS quality:', result.stdout)
        pids = [int(p.name.split('-')[1]) for p in self.state.glob('ready-*')
                if int(p.name.split('-')[1]) not in exclude]
        self.assertEqual(len(pids), children, 'real child readiness is mandatory')
        running = [pid for pid in pids if alive(pid)]
        self.assertEqual(running, [], 'quality returned with owned processes still running')
        (self.state / 'release').write_text('release', encoding='utf-8')
        time.sleep(.1)
        self.assertEqual((self.root / 'oracle.py').read_text(), 'assert True\n')
        self.assertFalse(any((self.state / ('done-' + str(pid))).exists() for pid in pids))

    def test_success_contains_children_before_integrity_and_return(self):
        self.assert_contained(self.invoke())

    def test_success_contains_three_generations(self):
        self.policy['checks'][0]['argv'].append('--grandchild')
        self.freeze()
        self.assert_contained(self.invoke(), children=4)

    def test_nonzero_exit_still_contains_owned_child(self):
        self.policy['checks'][0]['argv'].append('--fail')
        self.freeze()
        result = self.invoke()
        self.assertIn('exit 7', result.stderr)
        self.assert_contained(result, success=False, children=1)

    def test_timeout_rejects_and_contains_owned_child(self):
        self.policy['checks'][0].update(argv=[sys.executable, 'launcher.py', '--timeout'], timeout=5)
        self.freeze()
        before = time.monotonic()
        result = self.invoke()
        self.assertIn('timed out', result.stderr)
        self.assertLess(time.monotonic() - before, 12, 'one execution deadline plus shared cleanup grace')
        self.assert_contained(result, success=False, children=1)

    def test_neighbor_outside_check_job_survives_and_completes(self):
        neighbor = subprocess.Popen([sys.executable, str(self.root / 'worker.py'), '--neighbor'],
            cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: neighbor.wait(timeout=5))
        # LIFO: release before waiting, including an assertion failure.
        self.addCleanup(self.release_children)
        until = time.monotonic() + 10
        while not (self.state / ('ready-' + str(neighbor.pid))).exists() and time.monotonic() < until:
            time.sleep(.01)
        self.assertTrue((self.state / ('ready-' + str(neighbor.pid))).exists())
        result = self.invoke()
        self.assertTrue(alive(neighbor.pid), 'unrelated neighbor was terminated')
        self.assert_contained(result, exclude=(neighbor.pid,))
        neighbor.wait(timeout=5)
        self.assertTrue((self.state / ('done-' + str(neighbor.pid))).exists())

    def test_extracted_runner_without_neighbor_helper_uses_approved_git_blob(self):
        with tempfile.TemporaryDirectory(prefix='kdd-extracted-quality-') as directory:
            runner = Path(directory) / 'verify_quality.py'
            runner.write_bytes(subprocess.check_output(['git', '-C', str(self.root),
                'show', self.ref + ':scripts/verify_quality.py'], env=self.env, timeout=30))
            self.assertFalse(runner.with_name('process_tree.py').exists())
            self.assert_contained(self.invoke(runner))

    def test_candidate_helper_is_not_imported_as_trusted_runtime(self):
        self.write('scripts/process_tree.py', "raise RuntimeError('candidate helper must not execute')\n")
        self.assert_contained(self.invoke())

    def test_missing_approved_helper_rejects_before_checks(self):
        (self.root / 'scripts/process_tree.py').unlink()
        self.freeze()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('RUN ', result.stdout)
        self.assertNotIn('PASS quality:', result.stdout)
        self.assertFalse(list(self.state.glob('ready-*')))

    def test_git_symlink_helper_payload_rejects_before_checks(self):
        blob = self.git('rev-parse', 'HEAD:scripts/process_tree.py')
        self.git('update-index', '--cacheinfo', '120000,' + blob + ',scripts/process_tree.py')
        self.git('commit', '-qm', 'Synthetic invalid helper mode')
        self.ref = self.git('rev-parse', 'HEAD')
        self.assertTrue((self.root / 'scripts/process_tree.py').is_file())
        self.assertFalse((self.root / 'scripts/process_tree.py').is_symlink())
        self.assertTrue(self.git('ls-tree', self.ref, '--', 'scripts/process_tree.py').startswith('120000'))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('RUN ', result.stdout)
        self.assertFalse(list(self.state.glob('ready-*')))

    def test_regular_executable_git_helper_is_accepted(self):
        blob = self.git('rev-parse', 'HEAD:scripts/process_tree.py')
        self.git('update-index', '--cacheinfo', '100755,' + blob + ',scripts/process_tree.py')
        self.git('commit', '-qm', 'Synthetic regular executable helper')
        self.ref = self.git('rev-parse', 'HEAD')
        self.assert_contained(self.invoke())

    def test_synchronous_protected_write_still_rejects(self):
        self.policy['checks'][0]['argv'] = [sys.executable, '-c',
            "from pathlib import Path; Path('oracle.py').write_text('changed')"]
        self.freeze()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Protected file changed', result.stderr)
        self.assertNotIn('PASS quality:', result.stdout)

    def test_missing_executable_still_rejects_without_checks_passing(self):
        self.policy['checks'][0]['argv'] = ['kdd-quality-missing-program-779041']
        self.freeze()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('PASS quality:', result.stdout)
        self.assertFalse(list(self.state.glob('ready-*')))


if __name__ == '__main__':
    unittest.main()
