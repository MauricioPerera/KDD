"""Independent oracle for the project quality approval entry point."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_quality.py'


class QualityApproval(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git('init','-q')
        self.git('config','user.name','Quality Test')
        self.git('config','user.email','test@example.invalid')
        (self.root/'oracle.py').write_text('assert True\n',encoding='utf-8')
        (self.root/'app.py').write_text('value = 1\n',encoding='utf-8')
        self.policy = {'protected':['oracle.py'], 'implementation':['app.py'], 'pm':['report.txt'], 'required_kinds':['functional','adversarial'], 'checks':[
            {'name':'functional','kind':'functional','argv':[sys.executable,'oracle.py'],'timeout':5},
            {'name':'negative','kind':'adversarial','argv':[sys.executable,'-c','assert 1 + 1 == 2'],'timeout':5}]}
        self.freeze()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.PIPE).decode().strip()

    def freeze(self):
        (self.root/'quality.json').write_text(json.dumps(self.policy),encoding='utf-8')
        self.git('add','.')
        self.git('commit','-qm','approved oracle')
        self.ref=self.git('rev-parse','HEAD')

    def run_gate(self):
        return subprocess.run([sys.executable,str(SCRIPT),'--repo-root',str(self.root),'--policy','quality.json','--approved-ref',self.ref],capture_output=True,text=True,timeout=20)

    def test_approved_change_and_twice(self):
        self.policy['checks'][0]['argv']=[sys.executable,'-c',"from pathlib import Path; p=Path('report.txt'); p.write_text(p.read_text()+'x' if p.exists() else 'x')"]
        self.freeze()
        (self.root/'app.py').write_text('value = 2\n',encoding='utf-8')
        result=self.run_gate()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((self.root/'report.txt').read_text(),'xx')

    def test_untracked_rejected(self):
        (self.root/'outside.py').write_text('x=1\n')
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_staged_and_committed_outside_rejected(self):
        (self.root/'outside.py').write_text('x=1\n')
        self.git('add','outside.py')
        self.assertNotEqual(self.run_gate().returncode,0)
        self.git('commit','-qm','outside')
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_changed_oracle_rejected(self):
        (self.root/'oracle.py').write_text('assert False\n')
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_resigned_policy_rejected(self):
        self.policy['protected']=[]
        (self.root/'quality.json').write_text(json.dumps(self.policy))
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_fake_report_does_not_hide_failure(self):
        self.policy['checks'][0]['argv']=[sys.executable,'-c','raise SystemExit(7)']
        self.freeze()
        (self.root/'report.txt').write_text('PASS\n')
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_missing_required_ui_rejected(self):
        self.policy['required_kinds'].append('ui')
        self.freeze()
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_empty_checks_rejected(self):
        self.policy['checks']=[]
        self.freeze()
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_timeout_rejected(self):
        self.policy['checks'][0].update(argv=[sys.executable,'-c','import time; time.sleep(3)'],timeout=1)
        self.freeze()
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_path_escape_rejected(self):
        self.policy['protected']=['../outside.txt']
        self.freeze()
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_invalid_ref_rejected(self):
        self.ref='not-a-commit'
        self.assertNotEqual(self.run_gate().returncode,0)

    def test_missing_reference_argument_rejected(self):
        result=subprocess.run([sys.executable,str(SCRIPT),'--repo-root',str(self.root),'--policy','quality.json'],capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0)


if __name__=='__main__':
    unittest.main()
