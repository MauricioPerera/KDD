"""Bounded subprocess trees: POSIX sessions and Windows Jobs before execution."""
import json
import errno
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('timeout must be positive and finite')
    return value


class _WindowsJob:
    """An owned, non-inheritable Job handle, including nested runner Jobs."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self.c = ctypes
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        declarations = {
            'CreateJobObjectW': ([w.LPVOID, w.LPCWSTR], w.HANDLE),
            'SetInformationJobObject': ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
            'QueryInformationJobObject': ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID], w.BOOL),
            'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
            'TerminateJobObject': ([w.HANDLE, w.UINT], w.BOOL),
            'OpenProcess': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
            'CloseHandle': ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in declarations.items():
            function = getattr(self.k, name)
            function.argtypes, function.restype = args, result

        class BasicLimit(ctypes.Structure):
            _fields_ = [('user', ctypes.c_longlong), ('job', ctypes.c_longlong),
                        ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                        ('active', w.DWORD), ('affinity', ctypes.c_size_t),
                        ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [('basic', BasicLimit), ('io', ctypes.c_ulonglong * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [('times', ctypes.c_longlong * 4), ('faults', w.DWORD),
                        ('total', w.DWORD), ('active', w.DWORD), ('terminated', w.DWORD)]

        self.accounting = Accounting
        self.handle = self.k.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimit()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        try:
            self._check(self.k.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        except BaseException:
            self.close()
            raise

    def _check(self, ok):
        if not ok:
            raise self.c.WinError(self.c.get_last_error())

    def assign(self, pid):
        process = self.k.OpenProcess(0x0100 | 0x0001, False, pid)
        self._check(process)
        try:
            self._check(self.k.AssignProcessToJobObject(self.handle, process))
        finally:
            self.k.CloseHandle(process)

    def _members(self, deadline):
        capacity = 16
        while True:
            class ProcessIds(self.c.Structure):
                _fields_ = [('assigned', self.c.c_uint32), ('count', self.c.c_uint32),
                            ('ids', self.c.c_size_t * capacity)]

            info = ProcessIds()
            ok = self.k.QueryInformationJobObject(
                self.handle, 3, self.c.byref(info), self.c.sizeof(info), None)
            if not ok and self.c.get_last_error() != 234:  # ERROR_MORE_DATA
                self._check(ok)
            if ok and info.count == info.assigned and info.count <= capacity:
                return tuple(info.ids[:info.count])
            if time.monotonic() >= deadline:
                raise OSError('contained process list did not stabilize within cleanup grace')
            capacity = max(capacity * 2, info.assigned)

    def _retain_members(self, handles, deadline):
        for pid in self._members(deadline):
            if pid not in handles:
                handle = self.k.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
                self._check(handle)
                handles[pid] = handle

    def _close_members(self, handles):
        error = None
        for handle in handles.values():
            if not self.k.CloseHandle(handle):
                error = self.c.get_last_error()
        if error is not None:
            raise self.c.WinError(error)

    def _wait_members(self, handles, deadline):
        for handle in handles.values():
            remaining = max(0, math.ceil((deadline - time.monotonic()) * 1000))
            status = self.k.WaitForSingleObject(handle, min(remaining, 0xfffffffe))
            if status == 0xffffffff:  # WAIT_FAILED
                self._check(False)
            if status != 0:  # Only WAIT_OBJECT_0 confirms termination.
                raise OSError('contained process did not signal within cleanup grace')

    def terminate(self, deadline):
        if not self.handle:
            raise OSError('contained Job is already closed')
        handles = {}
        try:
            # The Job's active count can reach zero before process handles are
            # signaled. Retain owned members BEFORE asynchronous termination.
            self._retain_members(handles, deadline)
            self._check(self.k.TerminateJobObject(self.handle, 1))
            while True:
                self._retain_members(handles, deadline)
                info = self.accounting()
                self._check(self.k.QueryInformationJobObject(
                    self.handle, 1, self.c.byref(info), self.c.sizeof(info), None))
                if info.active == 0:
                    self._wait_members(handles, deadline)
                    return
                if time.monotonic() >= deadline:
                    raise OSError('contained process tree did not terminate within cleanup grace')
                time.sleep(min(.01, max(0, deadline - time.monotonic())))
        finally:
            self._close_members(handles)

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            self._check(self.k.CloseHandle(handle))


def _windows_child(directory):
    """Wait for Job assignment before starting ANY target or descendant."""
    directory = Path(directory)
    deadline = time.monotonic() + 30
    while not (directory / 'release').exists():
        if time.monotonic() >= deadline:
            return 1
        time.sleep(.005)
    spec = json.loads((directory / 'argv.json').read_text(encoding='utf-8'))
    try:
        result = subprocess.run(spec['argv'])
        status = {'returncode': result.returncode}
    except OSError as exc:
        status = {'errno': exc.errno, 'message': str(exc), 'filename': exc.filename}
    (directory / 'status.json').write_text(json.dumps(status), encoding='utf-8')
    return 0


def _stop(proc, job, deadline):
    if job is not None:
        job.terminate(deadline)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _capture_options(kwargs):
    options = dict(kwargs)
    if options.pop('capture_output', False):
        if 'stdout' in options or 'stderr' in options:
            raise ValueError('capture_output conflicts with stdout/stderr')
        options.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return options


def _drain(proc, deadline):
    try:
        return proc.communicate(timeout=max(.001, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as exc:
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()
        raise OSError('contained process pipes did not close within cleanup grace') from exc


def run(argv, *, cwd, timeout, **kwargs):
    """Return CompletedProcess, or fail after stopping and waiting owned children."""
    _positive(timeout)
    if not isinstance(argv, (list, tuple)) or not argv or kwargs.get('shell'):
        raise ValueError('argv must be a nonempty list without a shell')
    argv = [os.fspath(arg) for arg in argv]
    deadline = time.monotonic() + timeout
    if os.name == 'nt':
        # Match CreateProcess's synchronous missing-executable failure even with
        # a deadline shorter than the Python containment bootstrap startup.
        environment = kwargs.get('env')
        if environment is None:
            environment = os.environ
        if shutil.which(argv[0], path=environment.get('PATH', '')) is None:
            raise FileNotFoundError(errno.ENOENT, 'executable not found', argv[0])
    options = _capture_options(kwargs)
    job = proc = None
    cleanup_deadline = math.inf
    with tempfile.TemporaryDirectory(prefix='kdd-contained-') as temporary:
        directory = Path(temporary)
        try:
            if os.name == 'nt':
                job = _WindowsJob()
                (directory / 'argv.json').write_text(json.dumps({'argv': argv}), encoding='utf-8')
                bootstrap = [sys.executable, '-I', str(Path(__file__).resolve()),
                             '--contained-child', str(directory)]
                proc = subprocess.Popen(bootstrap, cwd=cwd, **options)
                job.assign(proc.pid)
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(argv, timeout)
                (directory / 'release').touch()
            else:
                proc = subprocess.Popen(argv, cwd=cwd, start_new_session=True, **options)
            try:
                stdout, stderr = proc.communicate(timeout=max(.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise subprocess.TimeoutExpired(argv, timeout, exc.output, exc.stderr) from exc
            cleanup_deadline = time.monotonic() + 5
            _stop(proc, job, cleanup_deadline)
            returncode = proc.returncode
            if job is not None:
                status = json.loads((directory / 'status.json').read_text(encoding='utf-8'))
                if 'errno' in status:
                    raise OSError(status['errno'], status['message'], status.get('filename'))
                returncode = status['returncode']
            return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
        except BaseException:
            if proc is not None:
                cleanup_deadline = min(cleanup_deadline, time.monotonic() + 5)
                _stop(proc, job, cleanup_deadline)
                if proc.poll() is None:
                    proc.kill()  # Also covers assignment failure before the release barrier.
                _drain(proc, cleanup_deadline)
            raise
        finally:
            if job is not None:
                job.close()


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--contained-child':
        raise SystemExit('internal contained-child entry only')
    raise SystemExit(_windows_child(sys.argv[2]))
