"""Real Git controls for independently cloned started perimeter fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import json, os, sys
import subprocess
from pathlib import Path
from tests.test_task_finish_perimeter import PerimeterCase
events=[]
def audit(event, args):
    if event != 'subprocess.Popen': return
    raw=args[1]
    text=' '.join(map(str,raw)) if isinstance(raw,(tuple,list)) else str(raw)
    if 'scripts/tasks.py' in text.replace('\\','/'):
        events.append(text)
sys.addaudithook(audit)
class ProbeCase(PerimeterCase): pass
before=len(events)
ProbeCase.setUpClass()
class_calls=events[before:]
fixture=getattr(ProbeCase,'started_fixture',None)
source=Path(fixture[0]) if fixture else None
def snapshot(root):
    commands=(('rev-parse','HEAD'),('show-ref',),('status','--porcelain=v1'))
    return ([subprocess.check_output(['git','-C',str(root),*cmd],text=True,encoding='utf8')
             for cmd in commands], (root/'.git/index').read_bytes())
source_before=snapshot(source) if source else None
source_has_no_evidence=(not list((source/'docs/task-evidence').glob('*.json'))) if source else False
cases=[]
try:
    per_case=[]
    for _ in range(2):
        case=ProbeCase('runTest')
        before=len(events)
        case.setUp()
        cases.append(case)
        per_case.append(events[before:])
    first,second=cases
    second_before=second.p.snapshot()
    first.integrate()
    outcome1=first.p.act('finish',1)
    second_unchanged=second.p.snapshot()==second_before
    marker1=first.marker.exists()
    marker2_before=second.marker.exists()
    second.integrate()
    outcome2=second.p.act('finish',1)
    print(json.dumps(dict(class_calls=class_calls, per_case=per_case,
        roots_distinct=first.p.root != second.p.root,
        second_unchanged=second_unchanged, marker1=marker1,
        marker2_before=marker2_before, marker2=second.marker.exists(),
        source_has_no_evidence=source_has_no_evidence,
        source_unchanged=(snapshot(source)==source_before) if source else False,
        status1=outcome1['task']['status'], status2=outcome2['task']['status'],
        evidence1=len(list((first.p.root/'docs/task-evidence').glob('*.json'))),
        evidence2=len(list((second.p.root/'docs/task-evidence').glob('*.json'))))))
finally:
    for case in reversed(cases): case.doCleanups()
    ProbeCase.doClassCleanups()
'''


class PostInitPerimeterSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = subprocess.run([sys.executable, '-X', 'utf8', '-c', PROBE], cwd=ROOT,
                           env=dict(os.environ, PYTHONUTF8='1'), capture_output=True,
                           text=True, encoding='utf-8', timeout=300)
        if p.returncode:
            raise AssertionError(p.stdout + p.stderr)
        cls.actual = json.loads(p.stdout)

    def test_preparation_runs_real_lifecycle_once_per_fixture_class(self):
        calls = self.actual['class_calls']
        for action in (' create ', ' ready ', ' start '):
            self.assertEqual(sum(action in (' ' + call + ' ') for call in calls), 1, calls)

    def test_case_setup_does_not_repeat_the_three_preparation_commands(self):
        for calls in self.actual['per_case']:
            self.assertEqual(calls, [], calls)

    def test_clones_remain_independent_when_one_task_closes(self):
        self.assertTrue(self.actual['roots_distinct'])
        self.assertTrue(self.actual['second_unchanged'])
        self.assertFalse(self.actual['marker2_before'])

    def test_seed_has_no_test_evidence_and_is_unchanged_by_clones(self):
        self.assertTrue(self.actual['source_has_no_evidence'])
        self.assertTrue(self.actual['source_unchanged'])

    def test_both_clones_run_real_oracles_and_generate_evidence(self):
        for suffix in ('1', '2'):
            self.assertEqual(self.actual['status' + suffix], 'done')
            self.assertTrue(self.actual['marker' + suffix])
            self.assertEqual(self.actual['evidence' + suffix], 1)


if __name__ == '__main__':
    unittest.main()
