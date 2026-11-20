"""Verify direct contained launch with actual process identity and I/O."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from time import monotonic, sleep
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'scripts/process_tree.py'
RUN = runpy.run_path(str(SOURCE))['run']
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
print(json.dumps(observed, ensure_ascii=False))
sys.stderr.write('error controlado á')
raise SystemExit(43)
"""
LIVE_CHILD = """
import os
from pathlib import Path
import sys
from time import sleep

directory = Path(sys.argv[1])
staged = directory / 'ready.tmp'
staged.write_text(str(os.getpid()), encoding='ascii')
staged.replace(directory / 'ready')
while not (directory / 'release').exists():
    sleep(.01)
"""


def observe_io(directory):
    project = directory / 'proyecto á con espacios'
    project.mkdir()
    input_path = directory / 'input.txt'
    input_path.write_bytes(INPUT.encode('utf-8'))
    argv = [sys.executable, '-I', '-B', '-X', 'utf8', '-c', IO_CHILD, *ARGUMENTS]
    with input_path.open('rb') as source:
        completed = RUN(argv, cwd=project, timeout=35, capture_output=True,
                        stdin=source, env=dict(os.environ, KDD_JOB_PROBE_VALUE=ENVIRONMENT),
                        text=True, encoding='utf-8')
    return dict(observed=json.loads(completed.stdout), caller=os.getpid(),
                expected_directory=str(project.resolve()), returncode=completed.returncode,
                stderr=completed.stderr, argv_preserved=completed.args == argv)


def is_in_job(pid, handle):
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                     ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    process = kernel.OpenProcess(0x1000, False, pid)
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        member = wintypes.BOOL()
        if not kernel.IsProcessInJob(process, handle, ctypes.byref(member)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(member.value)
    finally:
        if not kernel.CloseHandle(process):
            raise ctypes.WinError(ctypes.get_last_error())


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
        if os.name != 'nt' or sys.getwindowsversion().major >= 10:
            self.assertEqual(payload['parent'], row['caller'],
                             'the target must be a direct child of the caller')

    def test_direct_target_keeps_io_with_and_without_outer_containment(self):
        with tempfile.TemporaryDirectory(prefix='kdd-job-io-') as temporary:
            directory = Path(temporary)
            ordinary = observe_io(directory)
            argv = [sys.executable, '-I', '-B', '-X', 'utf8',
                    str(Path(__file__).resolve()), '--observe-io']
            outer = RUN(argv, cwd=directory, timeout=55, capture_output=True,
                        text=True, encoding='utf-8')
        self.assertEqual(outer.returncode, 0, outer.stderr)
        self.assertEqual(outer.stderr, '')
        for name, receipt in (('ordinary', ordinary), ('nested', json.loads(outer.stdout))):
            with self.subTest(caller=name):
                self.assert_io(receipt)

    def test_live_target_belongs_to_this_invocation(self):
        with tempfile.TemporaryDirectory(prefix='kdd-job-membership-') as temporary:
            directory = Path(temporary)
            owned = {}
            make_job = RUN.__globals__['_WindowsJob']

            def remember_job():
                job = make_job()
                owned['handle'] = job.handle
                return job

            argv = [sys.executable, '-I', '-B', '-c', LIVE_CHILD, str(directory)]
            ready = directory / 'ready'
            with patch.dict(RUN.__globals__, {'_WindowsJob': remember_job}):
                with ThreadPoolExecutor(1) as pool:
                    pending = pool.submit(RUN, argv, cwd=directory, timeout=30,
                                          capture_output=True)
                    try:
                        deadline = monotonic() + 15
                        while not ready.is_file() and not pending.done() and monotonic() < deadline:
                            sleep(.02)
                        self.assertTrue(ready.is_file(), 'target must indicate readiness')
                        pid = int(ready.read_text(encoding='ascii'))
                        self.assertGreater(pid, 0)
                        self.assertNotEqual(pid, os.getpid())
                        if os.name == 'nt':
                            self.assertIn('handle', owned)
                            self.assertTrue(is_in_job(pid, owned['handle']))
                        else:
                            self.assertEqual(os.getpgid(pid), pid)
                    finally:
                        (directory / 'release').touch()
                    completed = pending.result(timeout=35)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, b'')
        self.assertEqual(completed.stderr, b'')


if __name__ == '__main__':
    if sys.argv[1:] == ['--observe-io']:
        with tempfile.TemporaryDirectory(prefix='kdd-job-io-child-') as root:
            print(json.dumps(observe_io(Path(root))))
    else:
        unittest.main()
