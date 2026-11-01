"""Required restrictions through verify_quality cannot degrade to optional scans."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ASSURANCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ASSURANCE))
from tests import test_quality_oracle_reviews as fixtures

class RequiredProductControls(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.QualityOracleReviews()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.f.policy.pop('oracle_reviews')
        shutil.copyfile(ASSURANCE/'scripts/validate_budgets.py',self.f.root/'scripts/validate_budgets.py')
        self.f.policy['protected'].append('scripts/validate_budgets.py')
        self.entry={'id':'app-budget','contract':'knowledge/contracts/app.md','kind':'budget','mechanism':'python-ast'}
        self.f.policy['required_controls']=[self.entry]
        self.f.freeze()

    def reject(self,code):
        result=self.f.run_gate()
        self.assertNotEqual(result.returncode,0)
        self.assertIn(code,result.stdout+result.stderr)
        self.assertFalse((self.f.root/'checks.txt').exists())
        return result

    def test_required_supported_budget_records_two_actual_measurements(self):
        result=self.f.run_gate()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        reports=[json.loads(line.removeprefix('REQUIRED_CONTROL ')) for line in result.stdout.splitlines() if line.startswith('REQUIRED_CONTROL ')]
        self.assertEqual(len(reports),2)
        for number,row in enumerate(reports,1):
            self.assertEqual(row['iteration'],number)
            self.assertEqual(row['id'],'app-budget')
            self.assertEqual(row['status'],'PASS')
            self.assertEqual(row['mechanism'],'python-ast')
            self.assertEqual(row['scope'],'module-functions')
            self.assertEqual(row['functions_measured'],1)
            self.assertFalse(row['runtime_isolation'])
        self.assertEqual((self.f.root/'checks.txt').read_text().splitlines(),['check']*4)

    def test_required_runtime_network_restriction_without_enforcement_blocks(self):
        self.f.policy['required_controls']=[{'id':'deny-network','contract':'knowledge/contracts/app.md','kind':'forbid','capability':'network','mechanism':'runtime'}]
        self.f.freeze()
        self.reject('CONTROL_UNSUPPORTED')

    def test_required_unknown_budget_metric_blocks(self):
        text=self.f.contract.read_text(encoding='utf-8')
        self.f.contract.write_text(text.replace('  cyclomatic_max: 4','  cyclomatic_max: 4\n  memory_max: 8'),encoding='utf-8')
        self.f.freeze()
        self.reject('BUDGET_UNSUPPORTED')

    def test_real_budget_overrun_blocks_before_checks(self):
        text=self.f.contract.read_text(encoding='utf-8')
        self.f.contract.write_text(text.replace('  cyclomatic_max: 4','  cyclomatic_max: 1'),encoding='utf-8')
        self.f.freeze()
        self.reject('BUDGET_CYCLOMATIC')

    def test_required_measurement_runner_must_be_frozen(self):
        self.f.policy['protected'].remove('scripts/validate_budgets.py')
        self.f.freeze()
        self.reject('CONTROL_POLICY')

    def test_candidate_cannot_raise_the_approved_budget(self):
        text=self.f.contract.read_text(encoding='utf-8')
        self.f.contract.write_text(text.replace('  cyclomatic_max: 4','  cyclomatic_max: 400'),encoding='utf-8')
        self.reject('Protected file changed')

    def test_empty_required_control_inventory_is_not_a_pass(self):
        self.f.policy['required_controls']=[]
        self.f.freeze()
        self.reject('CONTROL_POLICY')

    def test_incomplete_contract_blocks_before_measurement(self):
        text=self.f.contract.read_text(encoding='utf-8')
        self.f.contract.write_text(text.replace('## Examples','## Removed examples'),encoding='utf-8')
        self.f.freeze()
        self.reject('CONTROL_CONTRACT')

    def test_required_budget_and_oracle_reviews_both_run_twice(self):
        self.f.policy['oracle_reviews']=[self.f.entry]
        self.f.freeze()
        result=self.f.run_gate()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        for prefix in ('REQUIRED_CONTROL ','ORACLE_REVIEW '):
            reports=[json.loads(line.removeprefix(prefix)) for line in result.stdout.splitlines() if line.startswith(prefix)]
            self.assertEqual(len(reports),2,prefix)
            self.assertEqual([row['iteration'] for row in reports],[1,2])
            self.assertTrue(all(row['status']=='PASS' for row in reports))
        self.assertEqual((self.f.root/'checks.txt').read_text().splitlines(),['check']*4)

    def test_existing_forbids_auditor_still_reports_unverified_without_enforcement_claim(self):
        result=subprocess.run([sys.executable,str(ASSURANCE/'scripts/audit_forbids.py'),str(self.f.root/'knowledge/contracts'),'--repo-root',str(self.f.root),'--strict'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('FORBID_UNVERIFIED',result.stdout)

    def test_check_cannot_approve_a_target_changed_after_its_measurement(self):
        self.f.write('quality/checks.py', "from pathlib import Path\np=Path('checks.txt')\np.write_text((p.read_text() if p.exists() else '')+'check\\n')\nPath('src/app.py').write_text('def accept(value):\\n return True\\n')\n")
        self.f.freeze()
        result=self.f.run_gate()
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('CONTROL_CHANGED',result.stdout+result.stderr)
        self.assertTrue((self.f.root/'checks.txt').exists(),'the real ordinary check must have run')
        self.assertEqual((self.f.root/'checks.txt').read_text().splitlines(),['check'])
        reports=[json.loads(line.removeprefix('REQUIRED_CONTROL ')) for line in result.stdout.splitlines() if line.startswith('REQUIRED_CONTROL ')]
        self.assertEqual(len(reports),1,'do not emit a second measurement of a different version')

    def test_duplicate_required_control_identity_blocks_before_checks(self):
        self.f.policy['required_controls'].append(dict(self.entry))
        self.f.freeze()
        self.reject('CONTROL_POLICY')

    def test_unknown_required_mechanism_cannot_fall_back_to_ast(self):
        self.entry['mechanism']='future-budget-engine'
        self.f.freeze()
        self.reject('CONTROL_UNSUPPORTED')

    def test_legacy_policy_reports_absence_of_required_control_guarantee(self):
        self.f.policy.pop('required_controls')
        self.f.freeze()
        result=self.f.run_gate()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('required controls not requested',result.stdout)
        self.assertFalse(any(line.startswith('REQUIRED_CONTROL ') for line in result.stdout.splitlines()))
        self.assertEqual((self.f.root/'checks.txt').read_text().splitlines(),['check']*4)

if __name__=='__main__':unittest.main()
