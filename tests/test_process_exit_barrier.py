"""Real owned forests and independent kernel handles; no simulated termination."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import gc
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('exit_barrier_runtime', ROOT / 'scripts/process_tree.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)

FOREST = r'''
import ctypes, json, os, subprocess, sys, time
from pathlib import Path
root, role, mode = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
deadline = time.monotonic() + 60
def wait(path):
    while not path.exists():
        if time.monotonic() >= deadline: sys.exit(91)
        time.sleep(.005)
if role == 0: wait(root / 'launch')
directory_handle = None
if os.name == 'nt':
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    directory_handle = kernel.CreateFileW(str(root), 0, 3, None, 3, 0x02000000, None)
    if directory_handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
if role < 2:
    subprocess.Popen([sys.executable, '-X', 'utf8', __file__, str(root), str(role + 1), mode],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
(root / ('ready-' + str(role))).write_text(str(os.getpid()), encoding='utf-8')
if role == 0 and mode == 'success':
    wait(root / 'finish-root')
    print(json.dumps({'cwd': os.getcwd(), 'token': os.environ['KDD_EXIT_TOKEN']}, ensure_ascii=False), flush=True)
    sys.exit(33)
wait(root / 'release-all')
(root / ('late-' + str(role))).write_text('survived', encoding='utf-8')
if directory_handle is not None: kernel.CloseHandle(directory_handle)
'''


class KernelObserver:
    """Separate handles owned by the oracle, never supplied to the runtime."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self.c = ctypes
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, arguments, result in (
                ('OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
                ('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD),
                ('CloseHandle', [w.HANDLE], w.BOOL),
                ('GetCurrentProcess', [], w.HANDLE),
                ('GetProcessHandleCount', [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL)):
            function = getattr(self.k, name)
            function.argtypes, function.restype = arguments, result
        self.handles = []

    def retain(self, pids):
        for pid in pids:
            handle = self.k.OpenProcess(0x00100000, False, pid)
            if not handle:
                raise self.c.WinError(self.c.get_last_error())
            self.handles.append(handle)

    def states(self):
        return [int(self.k.WaitForSingleObject(handle, 0)) for handle in self.handles]

    def count(self):
        value = self.c.c_ulong()
        if not self.k.GetProcessHandleCount(self.k.GetCurrentProcess(), self.c.byref(value)):
            raise self.c.WinError(self.c.get_last_error())
        return value.value

    def close(self):
        # Fixture cleanup is independent from the immediate assertion. A failed
        # oracle must not turn into a misleading TemporaryDirectory cleanup error.
        deadline = time.monotonic() + 5
        errors = []
        for handle in self.handles:
            status = self.k.WaitForSingleObject(handle, max(0, int((deadline - time.monotonic()) * 1000)))
            if status != 0:
                errors.append(int(status))
            if not self.k.CloseHandle(handle):
                errors.append('CloseHandle')
        self.handles.clear()
        if errors:
            raise AssertionError('Independent fixture cleanup failed: ' + repr(errors))


class ProcessExitBarrier(unittest.TestCase):
    @contextmanager
    def area(self):
        with tempfile.TemporaryDirectory(prefix='kdd exit barrier \u00f1 ') as temporary:
            root = Path(temporary)
            (root / 'forest.py').write_text(FOREST, encoding='utf-8')
            yield root

    def ready(self, root, operation=None):
        deadline = time.monotonic() + 8
        paths = [root / ('ready-' + str(number)) for number in range(3)]
        while not all(path.exists() and path.stat().st_size for path in paths):
            if operation is not None and operation.done():
                # Propagate a real launch/backend error rather than calling it
                # evidence of cancellation of a forest that never started.
                operation.result()
                self.fail('Operation completed before the forest was ready')
            if time.monotonic() >= deadline:
                self.fail('Three real generations did not acknowledge readiness')
            time.sleep(.005)
        pids = [int(path.read_text(encoding='utf-8')) for path in paths]
        self.assertEqual(len(set(pids)), 3)
        return pids

    def assert_no_late_effects(self, root):
        (root / 'release-all').touch()
        # An independent process supplies an observation window, not a sleep
        # interpreted as a Windows process-termination barrier.
        subprocess.run([sys.executable, '-c', 'import time;time.sleep(.12)'],
                       check=True, timeout=5, cwd=root)
        self.assertEqual(list(root.glob('late-*')), [])

    @contextmanager
    def owned_forest(self, root):
        job = RUNTIME._WindowsJob() if os.name == 'nt' else None
        observer = KernelObserver() if os.name == 'nt' else None
        proc = None
        try:
            proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(root / 'forest.py'),
                                     str(root), '0', 'hold'], cwd=root,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    start_new_session=os.name != 'nt')
            if job is not None:
                job.assign(proc.pid)
            (root / 'launch').touch()
            pids = self.ready(root)
            if observer is not None:
                observer.retain(pids)
            yield proc, job, observer
        finally:
            if job is not None:
                job.close()  # KILL_ON_JOB_CLOSE also protects failed assertions.
            elif proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if proc is not None:
                proc.wait(timeout=5)
            if observer is not None:
                observer.close()

    def cancel(self, root, proc, job, observer):
        deadline = time.monotonic() + 5
        RUNTIME._stop(proc, job, deadline)
        # Capture before waiting for the root: draining it can mask the missing
        # wait for another process owned by the Job.
        states = observer.states() if observer is not None else None
        RUNTIME._drain(proc, deadline)
        if states is not None:
            self.assertEqual(states, [0, 0, 0], 'Job returned before owned kernel handles signaled')
        else:
            self.assertIsNotNone(proc.returncode)
        self.assert_no_late_effects(root)

    def test_ready_forest_has_completed_kernel_exit_before_backend_return(self):
        for attempt in range(16):
            with self.subTest(attempt=attempt), self.area() as root:
                with self.owned_forest(root) as owned:
                    self.cancel(root, *owned)

    def test_public_success_and_timeout_close_background_members(self):
        for mode in ('success', 'timeout'):
            with self.subTest(mode=mode), self.area() as root:
                observer = KernelObserver() if os.name == 'nt' else None
                (root / 'launch').touch()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    operation = pool.submit(RUNTIME.run,
                        [sys.executable, '-X', 'utf8', str(root / 'forest.py'), str(root), '0', mode],
                        cwd=root, timeout=12 if mode == 'success' else 6,
                        capture_output=True, text=True, encoding='utf-8',
                        env=dict(os.environ, KDD_EXIT_TOKEN='se\u00f1al'))
                    try:
                        pids = self.ready(root, operation)
                        if observer is not None:
                            observer.retain(pids)
                        if mode == 'success':
                            (root / 'finish-root').touch()
                            result = operation.result(timeout=17)
                            self.assertEqual(result.returncode, 33)
                            self.assertEqual(json.loads(result.stdout),
                                             {'cwd': str(root), 'token': 'se\u00f1al'})
                        else:
                            with self.assertRaises(subprocess.TimeoutExpired):
                                operation.result(timeout=11)
                        if observer is not None:
                            self.assertEqual(observer.states(), [0, 0, 0])
                        self.assert_no_late_effects(root)
                    finally:
                        # Wait for the real bounded backend even if readiness or
                        # an assertion fails; only then release oracle handles.
                        try:
                            operation.result(timeout=17)
                        except subprocess.TimeoutExpired:
                            pass
                        finally:
                            if observer is not None:
                                observer.close()

    def test_unrelated_neighbor_still_completes(self):
        with self.area() as root:
            neighbor = subprocess.Popen([sys.executable, '-c',
                'import time;from pathlib import Path;'
                'p=Path("neighbor-release");d=time.monotonic()+15;'
                '\nwhile not p.exists() and time.monotonic()<d:time.sleep(.005)'
                '\nassert p.exists();print("neighbor completed")'],
                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                with self.owned_forest(root) as (proc, job, observer):
                    RUNTIME._stop(proc, job, time.monotonic() + 5)
                    RUNTIME._drain(proc, time.monotonic() + 5)
                    (root / 'neighbor-release').touch()
                    stdout, stderr = neighbor.communicate(timeout=8)
                    self.assertEqual(neighbor.returncode, 0, stderr)
                    self.assertEqual(stdout.strip(), b'neighbor completed')
                    self.assert_no_late_effects(root)
            finally:
                if neighbor.poll() is None:
                    neighbor.kill()
                    neighbor.communicate(timeout=5)

    def test_process_handles_are_released(self):
        observer = KernelObserver() if os.name == 'nt' else None
        descriptors = Path('/proc/self/fd') if Path('/proc/self/fd').is_dir() else Path('/dev/fd')
        def count():
            gc.collect()
            return observer.count() if observer is not None else len(list(descriptors.iterdir()))
        before = count()
        for attempt in range(8):
            with self.subTest(attempt=attempt), self.area() as root:
                with self.owned_forest(root) as (proc, job, handles):
                    RUNTIME._stop(proc, job, time.monotonic() + 5)
                    RUNTIME._drain(proc, time.monotonic() + 5)
                del proc, job, handles
        self.assertLessEqual(count(), before + 4, 'Owned handles/descriptors accumulated across real commands')

    def test_backend_failure_is_neither_timeout_nor_success(self):
        with self.area() as root:
            if os.name == 'nt':
                job = RUNTIME._WindowsJob()
                job.close()
                try:
                    with self.assertRaises(OSError) as raised:
                        job.terminate(time.monotonic() + 5)
                    self.assertNotIsInstance(raised.exception, subprocess.TimeoutExpired)
                finally:
                    job.close()
            else:
                with self.assertRaises(FileNotFoundError):
                    RUNTIME.run([sys.executable, '-c', 'raise AssertionError("must not start")'],
                                cwd=root / 'nonexistent', timeout=5)
            self.assertEqual(list(root.glob('ready-*')), [])


if __name__ == '__main__':
    unittest.main()
