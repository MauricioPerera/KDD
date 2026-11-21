"""Exercise process creation, fallback and live containment with real children."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from threading import local
from time import monotonic, sleep
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
from tests.test_process_exit_barrier import KernelObserver

RUN = runpy.run_path(str(ROOT / 'scripts/process_tree.py'))['run']
JOB_LIST = 0x2000D
NOT_SUPPORTED = 50
ACCESS_DENIED = 5
INVALID_PARAMETER = 87
INPUT = 'entrada por archivo: sí\n'
ENVIRONMENT = 'entorno explícito'
ARGUMENTS = ['literal & con espacios', 'comilla " final', 'dato café']
ERROR_TEXT = 'error controlado á'
IO_CHILD = """
import json
import os
from pathlib import Path
import sys
observed = dict(parent=os.getppid(), cwd=str(Path.cwd()),
                environment=os.environ['KDD_JOB_PROBE_VALUE'],
                arguments=sys.argv[1:], stdin=sys.stdin.read())
print(json.dumps(observed, ensure_ascii=False), flush=True)
sys.stderr.write('error controlado á')
raise SystemExit(43)
"""
LIVE_CHILD = """
import os
from pathlib import Path
import sys
from time import monotonic, sleep
directory = Path(sys.argv[1])
with (directory / 'started').open('ab') as marker:
    marker.write(b'x')
staged = directory / 'ready.tmp'
staged.write_text(str(os.getpid()), encoding='ascii')
staged.replace(directory / 'ready')
deadline = monotonic() + 25
while not (directory / 'release').exists():
    if monotonic() >= deadline:
        raise SystemExit(91)
    sleep(.01)
print('released')
"""
MARK_CHILD = """
from pathlib import Path
path = Path('started')
with path.open('ab') as marker:
    marker.write(b'x')
"""


def modern_windows():
    return os.name == 'nt' and sys.getwindowsversion().major >= 10


def observe_io(directory, merged=False):
    project = directory / 'proyecto á con espacios'
    project.mkdir()
    input_path = directory / 'input.txt'
    input_path.write_bytes(INPUT.encode('utf-8'))
    argv = [sys.executable, '-I', '-B', '-X', 'utf8', '-c', IO_CHILD, *ARGUMENTS]
    with input_path.open('rb') as source:
        options = dict(cwd=project, timeout=35, stdin=source,
                       env=dict(os.environ, KDD_JOB_PROBE_VALUE=ENVIRONMENT),
                       text=True, encoding='utf-8')
        if merged:
            output = directory / 'merged.txt'
            with output.open('wb') as stream:
                completed = RUN(argv, stdout=stream, stderr=subprocess.STDOUT, **options)
            body, error = output.read_text(encoding='utf-8').split('\n', 1)
            assert completed.stdout is None and completed.stderr is None
        else:
            completed = RUN(argv, capture_output=True, **options)
            body, error = completed.stdout, completed.stderr
    return dict(observed=json.loads(body), caller=os.getpid(),
                expected_directory=str(project.resolve()), returncode=completed.returncode,
                stderr=error, argv_preserved=completed.args == argv)


def member_of(kernel, process, job_handle):
    import ctypes
    from ctypes import wintypes as w

    check = kernel.IsProcessInJob
    check.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
    check.restype = w.BOOL
    member = w.BOOL()
    if not check(process, job_handle, ctypes.byref(member)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(member.value)


def observe_call(job, name, callback):
    original = getattr(job.k, name)

    def observed(*args):
        original.argtypes = observed.argtypes
        original.restype = observed.restype
        return callback(original, *args)

    observed.argtypes = original.argtypes
    observed.restype = original.restype
    setattr(job.k, name, observed)


def watch_creation(job, states):
    """Query the returned process before the real CreateProcessW caller resumes."""
    import ctypes
    from ctypes import wintypes as w

    def receipt(original, *args):
        created = original(*args)
        if created:
            # PROCESS_INFORMATION starts with hProcess, from the real call.
            handle = ctypes.cast(args[-1], ctypes.POINTER(w.HANDLE))[0]
            states.append(member_of(job.k, handle, job.handle))
        return created

    observe_call(job, 'CreateProcessW', receipt)


def finish_fault_fixture_child(job, creation_flags, process_info):
    """Wait for the controlled child and release its handles before reporting a simulated error."""
    from ctypes import wintypes as w

    handles = job.c.cast(process_info, job.c.POINTER(w.HANDLE))
    try:
        if creation_flags & 4:  # CREATE_SUSPENDED
            resume = job.k.ResumeThread
            resume.argtypes, resume.restype = [w.HANDLE], w.DWORD
            assert resume(handles[1]) == 1
        assert job.k.WaitForSingleObject(handles[0], 8000) == 0
    finally:
        for index in (1, 0):
            assert job.k.CloseHandle(handles[index])
            handles[index] = None


@contextmanager
def native_fault(stage, error, *, after_start=False):
    """Inject one native result while public RUN uses its real backend."""
    make_job = RUN.__globals__['_WindowsJob']
    calls = []

    def fault_binding():
        job = make_job()

        def set_attribute(original, *args):
            attribute = getattr(args[2], 'value', args[2])
            if stage != 'attribute' or attribute != JOB_LIST:
                return original(*args)
            calls.append('attribute')
            job.c.set_last_error(error)
            return False

        def create(original, *args):
            calls.append('creation')
            if stage != 'creation':
                return original(*args)
            if after_start:
                assert original(*args), job.c.WinError(job.c.get_last_error())
                flags = getattr(args[5], 'value', args[5])
                finish_fault_fixture_child(job, flags, args[-1])
            job.c.set_last_error(error)
            return False

        observe_call(job, 'UpdateProcThreadAttribute', set_attribute)
        observe_call(job, 'CreateProcessW', create)
        return job

    with patch.dict(RUN.__globals__, {'_WindowsJob': fault_binding}):
        yield calls


def ready_pid(directory, future):
    deadline = monotonic() + 6
    ready = directory / 'ready'
    while not ready.is_file():
        if future.done():
            future.result()
            raise AssertionError('RUN completed before its child became ready')
        if monotonic() >= deadline:
            raise AssertionError('the real child did not acknowledge readiness')
        sleep(.02)
    pid = int(ready.read_text(encoding='ascii'))
    assert pid > 0 and pid != os.getpid()
    return pid


def wait_posix_exit(pids):
    deadline = monotonic() + 5
    for pid in pids:
        while True:
            try:
                os.getpgid(pid)
            except ProcessLookupError:
                break
            if monotonic() >= deadline:
                raise AssertionError('the fixture child did not exit')
            sleep(.02)


@contextmanager
def live_targets(root, timeouts):
    """Keep each target alive until assertions and retain independent exit handles."""
    directories = {name: root / name for name in timeouts}
    for directory in directories.values():
        directory.mkdir()
    labels = local()
    records = {name: dict(at_creation=[]) for name in timeouts}
    make_job = RUN.__globals__['_WindowsJob']

    def remember_job():
        job = make_job()
        record = records[labels.name]
        record['handle'] = job.handle
        watch_creation(job, record['at_creation'])
        return job

    def launch(name, directory):
        labels.name = name
        argv = [sys.executable, '-I', '-B', '-c', LIVE_CHILD, str(directory)]
        return RUN(argv, cwd=root, timeout=timeouts[name], capture_output=True)

    owned = KernelObserver() if os.name == 'nt' else None
    pids = []
    with patch.dict(RUN.__globals__, {'_WindowsJob': remember_job}):
        with ThreadPoolExecutor(len(timeouts)) as pool:
            operations = {name: pool.submit(launch, name, directory)
                          for name, directory in directories.items()}
            try:
                for name, directory in directories.items():
                    pid = ready_pid(directory, operations[name])
                    pids.append(pid)
                    if owned is None:
                        records[name]['own_group'] = os.getpgid(pid) == pid
                    else:
                        # QUERY_LIMITED_INFORMATION plus SYNCHRONIZE.
                        handle = owned.k.OpenProcess(0x1000 | 0x100000, False, pid)
                        if not handle:
                            raise owned.c.WinError(owned.c.get_last_error())
                        owned.handles.append(handle)
                        records[name]['own_group'] = member_of(owned.k, handle, records[name]['handle'])
                yield records, operations, directories, owned
            finally:
                for directory in directories.values():
                    (directory / 'release').touch()
                if owned is not None:
                    owned.close()
                else:
                    wait_posix_exit(pids)


def observe_membership(directory):
    with live_targets(directory, {'child': 20}) as (records, operations, scopes, _):
        (scopes['child'] / 'release').touch()
        result = operations['child'].result(timeout=23)
    assert result.returncode == 0 and result.stdout.splitlines() == [b'released'] and not result.stderr
    return records['child']


def nested_receipt(mode, directory):
    argv = [sys.executable, '-I', '-B', '-X', 'utf8',
            str(Path(__file__).resolve()), mode]
    outer = RUN(argv, cwd=directory, timeout=55, capture_output=True,
                text=True, encoding='utf-8')
    assert outer.returncode == 0 and not outer.stderr, outer.stderr
    return json.loads(outer.stdout)


class ProcessJobAtCreation(unittest.TestCase):
    def assert_io(self, row):
        payload = row['observed']
        self.assertEqual(Path(payload['cwd']).resolve(), Path(row['expected_directory']))
        self.assertEqual(payload['environment'], ENVIRONMENT)
        self.assertEqual(payload['arguments'], ARGUMENTS)
        self.assertEqual(payload['stdin'], INPUT)
        self.assertEqual(row['stderr'], ERROR_TEXT)
        self.assertEqual(row['returncode'], 43)
        self.assertTrue(row['argv_preserved'])
        if os.name != 'nt' or modern_windows():
            self.assertEqual(payload['parent'], row['caller'],
                             'the target must be a direct child of the caller')

    def test_direct_target_keeps_io_with_and_without_outer_containment(self):
        with tempfile.TemporaryDirectory(prefix='kdd-job-io-') as temporary:
            directory = Path(temporary)
            merged = directory / 'merged'
            merged.mkdir()
            cases = [('ordinary', observe_io(directory)),
                     ('nested', nested_receipt('--observe-io', directory)),
                     ('merged', observe_io(merged, merged=True))]
        for name, receipt in cases:
            with self.subTest(caller=name):
                self.assert_io(receipt)

    def test_live_target_belongs_to_this_invocation(self):
        with tempfile.TemporaryDirectory(prefix='kdd-job-membership-') as temporary:
            directory = Path(temporary)
            ordinary = observe_membership(directory)
            nested = nested_receipt('--observe-membership', directory)
        for label, row in (('ordinary', ordinary), ('nested', nested)):
            with self.subTest(caller=label):
                self.assertTrue(row['own_group'])
                if modern_windows():
                    self.assertEqual(row['at_creation'], [True],
                                     'the real new target must already belong to its Job at creation')

    def test_only_confirmed_absent_native_capability_runs_the_legacy_job(self):
        with tempfile.TemporaryDirectory(prefix='kdd-job-unavailable-') as temporary:
            directory = Path(temporary)
            with native_fault('attribute', NOT_SUPPORTED) as calls:
                receipt = observe_membership(directory)
            self.assertTrue(receipt['own_group'])
            self.assertEqual(receipt['at_creation'], [])
            self.assertEqual((directory / 'child' / 'started').read_bytes(), b'x')
            if modern_windows():
                self.assertEqual(calls, ['attribute'])

    def test_backend_failure_does_not_restart_a_target(self):
        failures = [('attribute', ACCESS_DENIED, False), ('attribute', INVALID_PARAMETER, False),
                    ('creation', NOT_SUPPORTED, False), ('creation', NOT_SUPPORTED, True)]
        for stage, error, after_start in failures:
            with self.subTest(stage=stage, error=error, after_start=after_start):
                with tempfile.TemporaryDirectory(prefix='kdd-job-denied-') as temporary:
                    directory = Path(temporary)
                    marker = directory / 'started'
                    argv = [sys.executable, '-I', '-B', '-c', MARK_CHILD]
                    with native_fault(stage, error, after_start=after_start) as calls:
                        if modern_windows():
                            with self.assertRaises(OSError) as observed:
                                RUN(argv, cwd=directory, timeout=20)
                        else:
                            self.assertEqual(RUN(argv, cwd=directory, timeout=20).returncode, 0)
                    if modern_windows():
                        self.assertEqual(observed.exception.winerror, error)
                        self.assertEqual(calls, [stage])
                        if after_start:
                            self.assertEqual(marker.read_bytes(), b'x')
                        else:
                            self.assertFalse(marker.exists())
                    else:
                        self.assertEqual(marker.read_bytes(), b'x')

    def test_cancelled_invocation_leaves_its_concurrent_neighbor_running(self):
        with tempfile.TemporaryDirectory(prefix='kdd-job-concurrent-') as temporary:
            with live_targets(Path(temporary), {'short': 9, 'neighbor': 20}) as targets:
                records, tasks, scopes, observer = targets
                self.assertTrue(all(row['own_group'] for row in records.values()))
                if os.name == 'nt':
                    self.assertNotEqual(records['short']['handle'], records['neighbor']['handle'])
                with self.assertRaises(subprocess.TimeoutExpired):
                    tasks['short'].result(timeout=14)
                if observer is not None:
                    self.assertEqual(observer.states(), [0, 258],
                                     'the short target must exit while the neighbor is still alive')
                self.assertFalse(tasks['neighbor'].done())
                (scopes['neighbor'] / 'release').touch()
                surviving = tasks['neighbor'].result(timeout=8)
                self.assertEqual(surviving.returncode, 0, surviving.stderr)
                self.assertEqual(surviving.stdout.splitlines(), [b'released'])


if __name__ == '__main__':
    mode = sys.argv[1:]
    if mode in (['--observe-io'],['--observe-membership']):
        probe = observe_io if mode == ['--observe-io'] else observe_membership
        with tempfile.TemporaryDirectory(prefix='kdd-job-nested-') as temporary:
            print(json.dumps(probe(Path(temporary))))
    else:
        unittest.main()
