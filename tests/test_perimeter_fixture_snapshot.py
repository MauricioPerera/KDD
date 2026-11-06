"""Real Git isolation and preparation cost of perimeter fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PROBE=r"""
import json, os, sys, tempfile
from pathlib import Path
from tests.test_task_finish_perimeter import PerimeterProject
calls=[]
def audit(event,args):
    if event!='subprocess.Popen': return
    raw=args[1]
    tokens=[str(x).strip('\"') for x in raw] if isinstance(raw,(list,tuple)) else str(raw).split()
    if tokens and os.path.basename(tokens[0].strip('\"')).lower() in ('git','git.exe'):
        calls.append(tokens)
sys.addaudithook(audit)
with tempfile.TemporaryDirectory(prefix='kdd perimeter snapshot probe ') as area:
    root=Path(area)
    start=len(calls); first=PerimeterProject(root/'first'); calls1=calls[start:]
    first_ref=first.ref
    start=len(calls); second=PerimeterProject(root/'second'); calls2=calls[start:]
    second_ref=second.ref
    first.write('auxiliary.txt','first clone modified\n'); first.commit('First independent change')
    second_before=second.git('rev-parse','HEAD')
    second.marker=root/'second-marker'
    second.env['KDD_PERIMETER_PROBE']=str(second.marker)
    tip,result=second.complete(1)
    output={
      'first_inits':sum('init' in call for call in calls1),
      'second_inits':sum('init' in call for call in calls2),
      'first_clones':sum('clone' in call for call in calls1),
      'second_clones':sum('clone' in call for call in calls2),
      'first_ref':first_ref,'second_ref':second_ref,'second_before':second_before,
      'second_aux':(second.root/'auxiliary.txt').read_text(encoding='utf-8'),
      'first_aux':(first.root/'auxiliary.txt').read_text(encoding='utf-8'),
      'first_branch':first.git('branch','--show-current'),
      'second_status':result['task']['status'],
      'second_marker':second.marker.exists(),
      'evidence':(second.root/result['task']['evidence']).is_file(),
      'tip':tip,'name':second.git('config','--local','--get','user.name'),
      'maintenance':second.git('config','--local','--get','maintenance.auto'),
      'gc':second.git('config','--local','--get','gc.auto'),
    }
    print(json.dumps(output,sort_keys=True))
"""


class PerimeterFixtureSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result=subprocess.run([sys.executable,'-X','utf8','-c',PROBE],cwd=ROOT,
            env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,
            encoding='utf-8',timeout=300)
        if result.returncode: raise AssertionError(result.stdout+result.stderr)
        cls.data=json.loads(result.stdout)

    def test_one_preparation_and_two_real_clones(self):
        self.assertEqual(self.data['first_inits'],1)
        self.assertEqual(self.data['second_inits'],0)
        self.assertEqual(self.data['first_clones'],1)
        self.assertEqual(self.data['second_clones'],1)

    def test_clone_edits_and_history_are_independent(self):
        self.assertEqual(self.data['first_ref'],self.data['second_ref'])
        self.assertEqual(self.data['second_ref'],self.data['second_before'])
        self.assertEqual(self.data['first_aux'],'first clone modified\n')
        self.assertEqual(self.data['second_aux'],'existing unrelated product file\n')
        self.assertEqual(self.data['first_branch'],'main')

    def test_real_task_closes_with_own_evidence_and_oracle(self):
        self.assertEqual(self.data['second_status'],'done')
        self.assertTrue(self.data['second_marker'])
        self.assertTrue(self.data['evidence'])
        self.assertTrue(self.data['tip'])

    def test_concurrent_instances_remain_independent(self):
        from concurrent.futures import ThreadPoolExecutor
        from tests.test_task_finish_perimeter import PerimeterProject
        with tempfile.TemporaryDirectory(prefix='kdd perimeter concurrent ') as area:
            root=Path(area)
            with ThreadPoolExecutor(max_workers=2) as pool:
                first,second=list(pool.map(PerimeterProject,[root/'one',root/'two']))
            self.assertEqual(first.ref,second.ref)
            self.assertEqual(first.git('rev-parse','HEAD'),first.ref)
            self.assertEqual(second.git('rev-parse','HEAD'),second.ref)
            first.write('auxiliary.txt','independent concurrent clone\n')
            self.assertEqual((second.root/'auxiliary.txt').read_text(encoding='utf-8'),
                             'existing unrelated product file\n')

    def test_nested_parent_and_existing_workspace_preserve_original_behavior(self):
        from tests.test_task_finish_perimeter import PerimeterProject
        with tempfile.TemporaryDirectory(prefix='kdd perimeter compatibility ') as area:
            root=Path(area)
            nested=root/'new-parent'/'product'
            try:
                first=PerimeterProject(nested)
            except (OSError, subprocess.SubprocessError) as exc:
                self.fail('fresh nested root must be supported: '+str(exc))
            self.assertEqual(first.git('rev-parse','HEAD'),first.ref)
            existing=root/'existing'; existing.mkdir()
            sentinel=existing/'sentinel.txt'; sentinel.write_text('preserve',encoding='utf-8')
            try:
                second=PerimeterProject(existing)
            except (OSError, subprocess.SubprocessError) as exc:
                self.fail('existing workspace must be supported: '+str(exc))
            self.assertEqual(sentinel.read_text(encoding='utf-8'),'preserve')
            self.assertEqual(second.git('rev-parse','HEAD'),second.ref)

    def test_local_git_configuration_is_preserved(self):
        self.assertEqual(self.data['name'],'Simulated fixture reviewer')
        self.assertEqual(self.data['maintenance'],'false')
        self.assertEqual(self.data['gc'],'0')


if __name__=='__main__': unittest.main()
