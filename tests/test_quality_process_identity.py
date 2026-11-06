"""Native process-object controls for the frozen quality lifecycle oracle."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import ctypes, errno, json, os, select, subprocess, sys, time
from pathlib import Path
from tests import test_quality_process_lifecycle as fixture

mode = sys.argv[1]
case = fixture.QualityProcessLifecycle('runTest')
case.setUp()
phase = 'before'
late = []
original_alive = fixture.alive
def traced_alive(pid):
    if phase == 'returned': late.append(pid)
    return original_alive(pid)
fixture.alive = traced_alive
observer = getattr(case, 'observer', None)
observed = []
def native_state(resource):
    if os.name == 'nt':
        from ctypes import wintypes as w
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        kernel.WaitForSingleObject.restype = w.DWORD
        status = int(kernel.WaitForSingleObject(resource, 0))
        if status not in (0, 258): raise ctypes.WinError(ctypes.get_last_error())
        return status == 258
    poller = select.poll()
    poller.register(resource, select.POLLIN)
    events = poller.poll(0)
    if any(flags & select.POLLNVAL for _, flags in events):
        raise OSError(errno.EBADF, 'invalid observed process descriptor')
    return not events

if observer is not None:
    original_retain = observer.retain
    def traced_retain(pid):
        new = pid not in observer.resources
        original_retain(pid)
        if new:
            resource = observer.resources[pid]
            observed.append(dict(pid=pid, resource=int(resource),
                alive_at_capture=native_state(resource),
                acknowledged_before_capture=(case.state / ('observed-'+str(pid))).exists()))
    observer.retain = traced_retain

result = dict(mode=mode, observer_available=observer is not None)
neighbor = None
extra = None
try:
    if mode == 'identity':
        case.policy['checks'][0]['argv'].append('--grandchild')
        case.freeze()
        outcome = case.invoke()
        phase = 'returned'
        terminated=[not native_state(item['resource']) for item in observed]
        case.assert_contained(outcome, children=4)
        result.update(returncode=outcome.returncode, retained=observed,
            terminated=terminated,
            late_pid_probes=list(late), oracle=(case.root/'oracle.py').read_text())
    elif mode == 'neighbor':
        neighbor = subprocess.Popen([sys.executable, str(case.root/'worker.py'), '--neighbor'],
            cwd=case.root, env=case.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline=time.monotonic()+10
        while not (case.state/('ready-'+str(neighbor.pid))).exists() and time.monotonic()<deadline:
            time.sleep(.005)
        assert (case.state/('ready-'+str(neighbor.pid))).exists(), 'neighbor not ready'
        outcome=case.invoke()
        phase='returned'
        result['neighbor_alive_before_release']=neighbor.poll() is None
        result['neighbor_object_alive']=(native_state(observer.resources[neighbor.pid])
                                         if observer is not None else False)
        own=[item for item in observed if item['pid'] != neighbor.pid]
        result['owned_terminated']=[not native_state(item['resource']) for item in own]
        case.assert_contained(outcome, exclude=(neighbor.pid,))
        neighbor.wait(timeout=5)
        result.update(retained=observed, late_pid_probes=list(late),
            neighbor_done=(case.state/('done-'+str(neighbor.pid))).exists())
    elif mode == 'leak':
        helper=case.root/'scripts/process_tree.py'
        text=helper.read_text(encoding='utf-8')
        if os.name == 'nt':
            text=text.replace('limits.basic.flags = 0x2000', 'limits.basic.flags = 0')
            text=text.replace('self._check(self.k.TerminateJobObject(self.handle, 1))', 'return')
        else:
            text=text.replace('os.killpg(proc.pid, signal.SIGKILL)', 'pass')
        assert text != helper.read_text(encoding='utf-8'), 'unsafe control did not change helper'
        helper.write_text(text,encoding='utf-8')
        case.freeze()
        outcome=case.invoke()
        assert outcome.returncode == 0, outcome.stdout+outcome.stderr
        result['real_quality_claimed_pass']='PASS quality:' in outcome.stdout
        try:
            case.assert_contained(outcome)
        except AssertionError as error:
            result['leak_rejected']='owned processes still running' in str(error)
        else:
            result['leak_rejected']=False
        result['oracle_unchanged_at_observation']=(case.root/'oracle.py').read_text()=='assert True\n'
    elif mode == 'error':
        if observer is not None:
            neighbor=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            extra=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            observer.retain(neighbor.pid)
            observer.retain(extra.pid)
            resource=observer.resources[neighbor.pid]
            remaining=observer.resources[extra.pid]
            if os.name == 'nt':
                from ctypes import wintypes as w
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
                assert kernel.CloseHandle(resource)
            else:
                os.close(resource)
            try:
                observer.alive(neighbor.pid)
            except OSError:
                result['native_error_propagated']=True
            else:
                result['native_error_propagated']=False
            try:
                observer.close()
            except OSError:
                result['close_error_propagated']=True
            else:
                result['close_error_propagated']=False
            try:
                native_state(remaining)
            except OSError:
                result['other_resource_closed']=True
            else:
                result['other_resource_closed']=False
            result['resources_after_error']=len(observer.resources)
        else:
            result['native_error_propagated']=False
    elif mode == 'cleanup':
        outcome=case.invoke()
        case.assert_contained(outcome)
        resources=list(observer.resources.values()) if observer is not None else []
        case.doCleanups()
        closed=[]
        for resource in resources:
            try:
                native_state(resource)
            except OSError:
                closed.append(True)
            else:
                closed.append(False)
        result.update(resources=len(resources),all_resources_invalid=all(closed),
                      resources_remaining=len(observer.resources) if observer is not None else -1)
    else:
        raise AssertionError('unknown real probe')
finally:
    if extra is not None and extra.poll() is None:
        extra.kill()
        extra.wait(timeout=5)
    if neighbor is not None and neighbor.poll() is None:
        if mode == 'neighbor':
            (case.state/'release').touch()
        else:
            neighbor.kill()
        neighbor.wait(timeout=5)
    case.doCleanups()
print(json.dumps(result))
'''


class QualityProcessIdentity(unittest.TestCase):
    def probe(self, mode):
        environment = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', PROBE, mode],
            cwd=ROOT, env=environment, capture_output=True, text=True,
            encoding='utf-8', timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def test_original_objects_are_observed_alive_then_dead_without_late_pid_queries(self):
        actual = self.probe('identity')
        self.assertEqual(actual['returncode'], 0)
        self.assertEqual(len(actual['retained']), 4)
        self.assertTrue(all(item['alive_at_capture'] for item in actual['retained']))
        self.assertFalse(any(item['acknowledged_before_capture'] for item in actual['retained']))
        self.assertEqual(actual['terminated'], [True] * 4)
        self.assertEqual(actual['late_pid_probes'], [])
        self.assertEqual(actual['oracle'], 'assert True\n')

    def test_unrelated_neighbor_keeps_its_original_live_object_and_completes(self):
        actual = self.probe('neighbor')
        self.assertTrue(actual['neighbor_alive_before_release'])
        self.assertTrue(actual['neighbor_object_alive'])
        self.assertEqual(actual['owned_terminated'], [True, True])
        self.assertEqual(len(actual['retained']), 3)
        self.assertEqual(actual['late_pid_probes'], [])
        self.assertTrue(actual['neighbor_done'])

    def test_real_uncontained_children_still_reject_a_successful_quality_command(self):
        actual = self.probe('leak')
        self.assertTrue(actual['real_quality_claimed_pass'])
        self.assertTrue(actual['leak_rejected'])
        self.assertTrue(actual['oracle_unchanged_at_observation'])

    def test_invalid_native_object_is_an_error_instead_of_a_dead_process(self):
        actual = self.probe('error')
        self.assertTrue(actual['observer_available'])
        self.assertTrue(actual['native_error_propagated'])
        self.assertTrue(actual['close_error_propagated'])
        self.assertTrue(actual['other_resource_closed'])
        self.assertEqual(actual['resources_after_error'], 0)

    def test_fixture_cleanup_closes_every_retained_native_resource(self):
        actual = self.probe('cleanup')
        self.assertEqual(actual['resources'], 2)
        self.assertTrue(actual['all_resources_invalid'])
        self.assertEqual(actual['resources_remaining'], 0)


if __name__ == '__main__':
    unittest.main()
