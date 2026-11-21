"""Bounded subprocess trees: POSIX sessions and Windows Jobs before execution."""
from contextlib import ExitStack, contextmanager
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

if os.name == 'nt':
    import _winapi
    import ctypes
    from ctypes import wintypes as w

    class _StartupInfo(ctypes.Structure):
        _fields_ = [
            ('size', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR), ('title', w.LPWSTR),
            ('x', w.DWORD), ('y', w.DWORD), ('width', w.DWORD), ('height', w.DWORD),
            ('columns', w.DWORD), ('rows', w.DWORD), ('fill', w.DWORD), ('flags', w.DWORD),
            ('show', w.WORD), ('reserved_count', w.WORD), ('reserved_bytes', w.LPVOID),
            ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE),
        ]

    class _StartupInfoEx(ctypes.Structure):
        _fields_ = [('info', _StartupInfo), ('attributes', w.LPVOID)]

    class _ProcessInformation(ctypes.Structure):
        _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]

_JOB_LIST = 0x2000D  # PROC_THREAD_ATTRIBUTE_JOB_LIST
_HANDLE_LIST = 0x20002  # PROC_THREAD_ATTRIBUTE_HANDLE_LIST
_NOT_SUPPORTED = 50
_SUSPENDED = 0x4
_UNICODE_ENVIRONMENT = 0x400
_EXTENDED_STARTUP = 0x80000


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


@contextmanager
def _windows_job_attributes(job):
    kernel = job.k
    size_pointer = ctypes.POINTER(ctypes.c_size_t)
    for name, arguments, result in (
        ('InitializeProcThreadAttributeList', [w.LPVOID, w.DWORD, w.DWORD, size_pointer], w.BOOL),
        ('UpdateProcThreadAttribute', [w.LPVOID, w.DWORD, ctypes.c_size_t, w.LPVOID,
                                      ctypes.c_size_t, w.LPVOID, size_pointer], w.BOOL),
        ('DeleteProcThreadAttributeList', [w.LPVOID], None),
        ('CreateProcessW', [w.LPCWSTR, w.LPWSTR, w.LPVOID, w.LPVOID, w.BOOL, w.DWORD, w.LPVOID,
                            w.LPCWSTR, ctypes.POINTER(_StartupInfoEx),
                            ctypes.POINTER(_ProcessInformation)], w.BOOL),
        ('ResumeThread', [w.HANDLE], w.DWORD),
    ):
        function = getattr(kernel, name)
        function.argtypes, function.restype = arguments, result
    size = ctypes.c_size_t()
    kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
    job._check(size.value)
    attributes = ctypes.create_string_buffer(size.value)
    job._check(kernel.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)))
    job_list = (w.HANDLE * 1)(job.handle)
    try:
        supported = kernel.UpdateProcThreadAttribute(
            attributes, 0, _JOB_LIST, job_list, ctypes.sizeof(job_list), None, None)
        if not supported and ctypes.get_last_error() == _NOT_SUPPORTED:
            yield None
        else:
            job._check(supported)
            # The values supplied to the list must outlive its deletion.
            yield attributes
    finally:
        kernel.DeleteProcThreadAttributeList(attributes)


def _windows_environment(environment):
    if environment is None:
        return None
    entries = {}
    for key, value in environment.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError('Windows environment names and values must be strings')
        if not key or '=' in key[1:] or '\0' in key or '\0' in value:
            raise ValueError('invalid Windows environment entry')
        entries.setdefault(key.upper(), key + '=' + value)
    block = '\0'.join(entries[key] for key in sorted(entries))
    return ctypes.create_unicode_buffer(block + '\0')


def _windows_startup(startupinfo, pipes):
    supplied = startupinfo or subprocess.STARTUPINFO()
    native = _StartupInfoEx()
    native.info.size = ctypes.sizeof(native)
    native.info.flags = supplied.dwFlags
    native.info.show = supplied.wShowWindow
    handles = list((supplied.lpAttributeList or {}).get('handle_list', ()))
    standard = (pipes[0], pipes[3], pipes[5])  # Child ends of stdin, stdout and stderr.
    if -1 not in standard:
        native.info.flags |= _winapi.STARTF_USESTDHANDLES
        native.info.stdin, native.info.stdout, native.info.stderr = map(int, standard)
        handles.extend(map(int, standard))
    else:
        native.info.stdin = supplied.hStdInput
        native.info.stdout = supplied.hStdOutput
        native.info.stderr = supplied.hStdError
    return native, handles


class _WindowsJobPopen(subprocess.Popen):
    """Use Popen's Windows pipe and wait machinery around a per-Job CreateProcessW."""
    def __init__(self, argv, *, job, attributes, **options):
        self._job = job
        self._attributes = attributes
        self._initial_thread = None
        try:
            super().__init__(argv, **options)
        except BaseException:
            self.close_initial_thread()
            raise

    def _execute_child(self, args, executable, *launch):
        # CPython's Windows Popen supplies these positional arguments, then six
        # pipe ends and the POSIX-only settings that Windows ignores.
        (_preexec, _close_fds, pass_fds, cwd, env, startupinfo, creationflags, _shell,
         p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite, *_posix) = launch
        job = self._job
        pipes = (p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite)
        try:
            if pass_fds:
                raise ValueError('pass_fds is unavailable on Windows')
            native, handles = _windows_startup(startupinfo, pipes)
            # KDD invocations can overlap. Only the explicitly named ends are inherited.
            handles = self._filter_handle_list(handles)
            if handles:
                handles = (w.HANDLE * len(handles))(*handles)
                self._attributes.inherited_handles = handles
                job._check(job.k.UpdateProcThreadAttribute(
                    self._attributes, 0, _HANDLE_LIST, handles, ctypes.sizeof(handles), None, None))
            native.attributes = ctypes.addressof(self._attributes)
            application = os.fsdecode(executable)
            if application.lower().endswith(('.cmd', '.bat')):
                args, application = [application, *args[1:]], None
            command = subprocess.list2cmdline(args)
            cwd = os.fsdecode(cwd) if cwd is not None else None
            if '\0' in command or (cwd is not None and '\0' in cwd):
                raise ValueError('embedded null character')
            sys.audit('subprocess.Popen', application, command, cwd, env)
            sys.audit('_winapi.CreateProcess', application, command, cwd)
            information = _ProcessInformation()
            flags = creationflags | _EXTENDED_STARTUP | _UNICODE_ENVIRONMENT | _SUSPENDED
            job._check(job.k.CreateProcessW(
                application, ctypes.create_unicode_buffer(command), None, None, bool(handles), flags,
                _windows_environment(env), cwd, ctypes.byref(native), ctypes.byref(information)))
            self._handle = subprocess.Handle(information.process)
            self._initial_thread = subprocess.Handle(information.thread)
            self.pid = information.pid
            self._child_created = True
        finally:
            self._close_pipe_fds(*pipes)

    def resume(self):
        self._job._check(self._job.k.ResumeThread(self._initial_thread) != 0xffffffff)

    def close_initial_thread(self):
        if self._initial_thread is not None:
            self._initial_thread.Close()
            self._initial_thread = None


def _start_windows_job_target(argv, *, cwd, job, options):
    if sys.getwindowsversion().major < 10:
        return None
    if options.get('creationflags', 0) & _winapi.CREATE_BREAKAWAY_FROM_JOB:
        raise ValueError('a contained process cannot break away from its parent Job')
    with _windows_job_attributes(job) as attributes:
        if attributes is None:
            return None
        return _WindowsJobPopen(argv, cwd=cwd, job=job, attributes=attributes, **options)


def _windows_executable(command, cwd, environment):
    """Resolve in the target's directory and environment, as the former Python parent did."""
    command = os.fsdecode(command)
    directory = os.path.abspath(os.fsdecode(cwd) if cwd is not None else os.getcwd())
    if os.path.dirname(command):
        locations = [directory]
        filename = command
    else:
        system = os.environ.get('SystemRoot')
        system_directories = [os.path.join(system, part) for part in ('System32', 'System', '')] if system else []
        path = next((value for key, value in environment.items() if key.upper() == 'PATH'), '')
        locations = [os.path.dirname(sys.executable), directory, *system_directories, *path.split(os.pathsep)]
        filename = command + '.exe' if command and not os.path.splitext(command)[1] else command
    for location in locations:
        path = os.path.join(directory, location.strip('"'), filename)
        executable = shutil.which(path)
        if executable is not None:
            return executable
    raise FileNotFoundError(errno.ENOENT, 'executable not found', command)


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


def _release_windows_target(proc, legacy_directory, options):
    if legacy_directory is not None:
        (legacy_directory / 'release').touch()
        return
    if not options.get('creationflags', 0) & _SUSPENDED:
        proc.resume()
    proc.close_initial_thread()


def run(argv, *, cwd, timeout, **kwargs):
    """Return CompletedProcess, or fail after stopping and waiting owned children."""
    _positive(timeout)
    if not isinstance(argv, (list, tuple)) or not argv or kwargs.get('shell'):
        raise ValueError('argv must be a nonempty list without a shell')
    argv = [os.fspath(arg) for arg in argv]
    deadline = time.monotonic() + timeout
    options = _capture_options(kwargs)
    job = proc = None
    legacy_directory = None
    cleanup_deadline = math.inf
    with ExitStack() as resources:
        try:
            if os.name == 'nt':
                environment = options.get('env')
                executable = _windows_executable(argv[0], cwd, os.environ if environment is None else environment)
                job = _WindowsJob()
                proc = _start_windows_job_target(argv, cwd=cwd, job=job,
                                                 options=dict(options, executable=executable))
                if proc is None:
                    legacy_directory = Path(resources.enter_context(tempfile.TemporaryDirectory(prefix='kdd-contained-')))
                    (legacy_directory / 'argv.json').write_text(json.dumps({'argv': argv}), encoding='utf-8')
                    bootstrap = [sys.executable, '-I', str(Path(__file__).resolve()),
                                 '--contained-child', str(legacy_directory)]
                    proc = subprocess.Popen(bootstrap, cwd=cwd, **options)
                    job.assign(proc.pid)
                else:
                    resources.callback(proc.close_initial_thread)
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(argv, timeout)
                _release_windows_target(proc, legacy_directory, options)
            else:
                proc = subprocess.Popen(argv, cwd=cwd, start_new_session=True, **options)
            try:
                stdout, stderr = proc.communicate(timeout=max(.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise subprocess.TimeoutExpired(argv, timeout, exc.output, exc.stderr) from exc
            cleanup_deadline = time.monotonic() + 5
            _stop(proc, job, cleanup_deadline)
            returncode = proc.returncode
            if legacy_directory is not None:
                status = json.loads((legacy_directory / 'status.json').read_text(encoding='utf-8'))
                if 'errno' in status:
                    raise OSError(status['errno'], status['message'], status.get('filename'))
                returncode = status['returncode']
            return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
        except BaseException:
            if job is not None or proc is not None:
                cleanup_deadline = min(cleanup_deadline, time.monotonic() + 5)
                _stop(proc, job, cleanup_deadline)
            if proc is not None:
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
