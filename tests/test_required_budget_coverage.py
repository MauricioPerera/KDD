"""Required budget measurement must report real coverage, not empty OK."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests import test_mutation_control_evidence as support

class RequiredBudgetCoverage(unittest.TestCase):
    def setUp(self):
        self.root,self.contract,self.area=support.MutationControls.project(self)

    def run_budget(self,selector='app'):
        return subprocess.run([sys.executable,str(ROOT/'scripts/validate_budgets.py'),
            str(self.root/'knowledge/contracts'),'--repo-root',str(self.root),
            '--contract',selector,'--required','--json'],capture_output=True,
            text=True,encoding='utf-8',timeout=10)

    def reject(self,code):
        result=self.run_budget()
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn(code,result.stdout+result.stderr)
        return result

    def test_required_missing_selector_is_not_zero_coverage_success(self):
        result=self.run_budget('unknown-contract')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('BUDGET_COVERAGE',result.stdout+result.stderr)

    def test_required_missing_target_is_not_silently_omitted(self):
        (self.root/'src/app.py').unlink()
        self.reject('BUDGET_TARGET')

    def test_required_unsupported_language_is_not_silently_omitted(self):
        text=self.contract.read_text(encoding='utf-8')
        self.contract.write_text(text.replace('src/app.py','src/app.ts'),encoding='utf-8')
        (self.root/'src/app.ts').write_text('export const accept=(value:number)=>value===1;\n',encoding='utf-8')
        self.reject('BUDGET_UNSUPPORTED')

    def test_required_zero_measured_functions_is_not_success(self):
        (self.root/'src/app.py').write_text('value=1\n',encoding='utf-8')
        self.reject('BUDGET_COVERAGE')

    def test_required_unknown_metric_is_not_ignored(self):
        text=self.contract.read_text(encoding='utf-8')
        self.contract.write_text(text.replace('  cyclomatic_max: 4','  cyclomatic_max: 4\n  memory_max: 8'),encoding='utf-8')
        self.reject('BUDGET_UNSUPPORTED')

    def test_required_invalid_python_is_a_measurement_error(self):
        (self.root/'src/app.py').write_text('def broken(:\n',encoding='utf-8')
        self.reject('BUDGET_PARSE')

    def test_supported_measurement_identifies_scope_source_and_metrics(self):
        result=self.run_budget()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['contracts_checked'],1)
        self.assertEqual(report['functions_measured'],1)
        row=report['measurements'][0]
        self.assertEqual(row['method'],'python-ast')
        self.assertEqual(row['language'],'python')
        self.assertEqual(row['scope'],'module-functions')
        self.assertEqual(row['target'],'src/app.py')
        self.assertEqual(row['target_sha256'],hashlib.sha256(support.TARGET.encode()).hexdigest())
        self.assertEqual(row['functions'][0]['name'],'accept')
        self.assertEqual(row['functions'][0]['metrics']['cyclomatic_max'],2)
        self.assertEqual(row['functions'][0]['metrics']['params_max'],1)

    def test_real_overrun_retains_its_measurement_in_failed_report(self):
        text=self.contract.read_text(encoding='utf-8')
        self.contract.write_text(text.replace('  cyclomatic_max: 4','  cyclomatic_max: 1'),encoding='utf-8')
        result=self.reject('BUDGET_CYCLOMATIC')
        report=json.loads(result.stdout)
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(report['functions_measured'],1)
        row=report['measurements'][0]
        self.assertEqual(row['functions'][0]['metrics']['cyclomatic_max'],2)
        self.assertEqual(row['budget']['cyclomatic_max'],1)

    def test_explicit_non_python_language_is_not_measured_as_python(self):
        text=self.contract.read_text(encoding='utf-8')
        self.contract.write_text(text.replace('target: src/app.py','language: typescript\ntarget: src/app.py'),encoding='utf-8')
        self.reject('BUDGET_UNSUPPORTED')

    def test_non_regular_target_is_not_a_supported_measurement(self):
        path=self.root/'src/app.py'
        path.unlink()
        path.mkdir()
        self.reject('BUDGET_TARGET')

    def test_source_hash_declares_line_ending_normalization(self):
        (self.root/'src/app.py').write_bytes(support.TARGET.replace('\n','\r\n').encode())
        result=self.run_budget()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        row=json.loads(result.stdout)['measurements'][0]
        self.assertEqual(row['hash_method'],'sha256-lf')
        self.assertEqual(row['target_sha256'],hashlib.sha256(support.TARGET.encode()).hexdigest())

if __name__=='__main__':unittest.main()
