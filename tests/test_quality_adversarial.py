"""Supplemental review cases, separate from the frozen implementation oracle."""
import sys
import unittest
from tests import test_verify_quality as fixtures


class QualityAdversarial(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.QualityApproval()
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_check_cannot_create_outside_file(self):
        c=self.case
        c.policy['checks'][0]['argv']=[sys.executable,'-c',"from pathlib import Path; Path('outside.py').write_text('x=1')"]
        c.freeze()
        result=c.run_gate()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Outside approved perimeter',result.stderr)

    def test_check_cannot_rewrite_oracle(self):
        c=self.case
        c.policy['checks'][0]['argv']=[sys.executable,'-c',"from pathlib import Path; Path('oracle.py').write_text('assert False')"]
        c.freeze()
        result=c.run_gate()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Protected file changed',result.stderr)

    def test_staged_oracle_hidden_by_restored_worktree(self):
        c=self.case
        path=c.root/'oracle.py'
        original=path.read_bytes()
        path.write_text('assert False\n')
        c.git('add','oracle.py')
        path.write_bytes(original)
        result=c.run_gate()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Protected index changed',result.stderr)

    def test_missing_executable_rejected(self):
        c=self.case
        c.policy['checks'][0]['argv']=['kdd-missing-executable-71945']
        c.freeze()
        self.assertNotEqual(c.run_gate().returncode,0)

    def test_boolean_timeout_is_not_an_integer_budget(self):
        c=self.case
        c.policy['checks'][0]['timeout']=True
        c.freeze()
        self.assertNotEqual(c.run_gate().returncode,0)


if __name__=='__main__':
    unittest.main()
