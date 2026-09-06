"""Execute the actual workflow's Python approval step on temporary projects."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import unittest
from tests import test_verify_quality as fixtures

ROOT=Path(__file__).resolve().parents[1]


class QualityWorkflow(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.QualityApproval()
        self.case.setUp()
        workflow=(ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8')
        step=workflow.split('      - name: Approve project quality (when configured)\n',1)[1].split('      - name:',1)[0]
        self.body=textwrap.dedent(step.split('        run: |\n',1)[1])

    def tearDown(self):
        self.case.tearDown()

    def run_step(self,policy,ref):
        env=dict(os.environ,KDD_QUALITY_POLICY=policy,KDD_QUALITY_APPROVED_REF=ref)
        return subprocess.run([sys.executable,'-c',self.body],cwd=self.case.root,env=env,capture_output=True,text=True,timeout=20)

    def test_policy_without_approval_fails(self):
        result=self.run_step('quality.json','')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('explicitly approved reference',result.stderr)

    def test_unconfigured_template_is_explicit_skip(self):
        result=self.run_step('missing.json','')
        self.assertEqual(result.returncode,0)
        self.assertIn('SKIP:',result.stdout)
        self.assertNotIn('PASS',result.stdout)

    def test_configured_project_executes_real_gate(self):
        c=self.case
        (c.root/'scripts').mkdir()
        shutil.copy2(ROOT/'scripts/verify_quality.py',c.root/'scripts/verify_quality.py')
        c.policy['protected'].append('scripts/verify_quality.py')
        c.freeze()
        result=self.run_step('quality.json',c.ref)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('PASS quality',result.stdout)


if __name__=='__main__':
    unittest.main()
