"""Actual sealed oracles and CLI commands exercise portable quoting."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from tests import test_mutation_control_evidence as support

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mutation_audit as audit


class MutationCommandQuoting(unittest.TestCase):
    def setUp(self):
        fixture=support.MutationControls('test_broken_original_import_rejects_before_mutants')
        self.addCleanup(fixture.doCleanups)
        self.root,self.contract,self.area=fixture.project()
        self.text=self.contract.read_text(encoding='utf-8')

    def run_command(self,command,oracle='tests/test_app.py'):
        digest=hashlib.sha256((self.root/oracle).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        text=self.text.replace('python -m unittest tests/test_app.py',command)
        text=text.replace(hashlib.sha256(support.STRONG.encode()).hexdigest(),digest)
        text=text.replace('tests: tests/test_app.py',"tests: '"+oracle+"'")
        self.contract.write_text(text,encoding='utf-8')
        return audit.audit_contract(str(self.contract),str(self.root),timeout=10)

    def verified(self,result):
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['detected'],3)
        self.assertEqual([c['status'] for c in result['controls']],['PASS','PASS'])

    def test_quoted_oracle_has_same_real_detections_as_unquoted(self):
        self.verified(self.run_command('python -m unittest "tests/test_app.py"'))
        self.verified(self.run_command('python -m unittest tests/test_app.py'))

    def test_unquoted_control_executes_the_original_oracle(self):
        self.verified(self.run_command('python -m unittest tests/test_app.py'))

    def test_absolute_quoted_python_executes_real_oracle(self):
        self.verified(self.run_command('"'+sys.executable+'" -m unittest "tests/test_app.py"'))

    def test_quoted_script_path_with_spaces_and_unicode_executes(self):
        script=self.root/'tests/oracle space \u00f1.py'
        script.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[1]))\n'+
            support.STRONG+'\nif __name__ == "__main__":unittest.main()\n',encoding='utf-8')
        self.verified(self.run_command('python "tests/oracle space \u00f1.py"','tests/oracle space \u00f1.py'))

    def test_actual_arguments_are_preserved_without_shell_expansion(self):
        script=self.root/'tests/argument oracle.py'
        script.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[1]))\nassert sys.argv[1:]==["two words","literal&value"]\n'+
            support.STRONG+'\nif __name__=="__main__":unittest.main(argv=[sys.argv[0]])\n',encoding='utf-8')
        self.verified(self.run_command('python "tests/argument oracle.py" "two words" "literal&value"','tests/argument oracle.py'))

    def test_quoted_failing_original_remains_inconclusive_not_detected(self):
        (self.root/'tests/test_app.py').write_text('raise RuntimeError("real original failure")\n',encoding='utf-8')
        result=self.run_command('python -m unittest "tests/test_app.py"')
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['detected'],0)
        self.assertEqual(result['mutants'],[]);self.assertEqual(result['controls'][0]['status'],'INCONCLUSIVE')

    def test_quoted_uncovered_mutants_still_survive(self):
        oracle='import unittest\nclass Unrelated(unittest.TestCase):\n def test_control(self):self.assertEqual(7,7)\n'
        (self.root/'tests/test_app.py').write_text(oracle,encoding='utf-8')
        result=self.run_command('python -m unittest "tests/test_app.py"')
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['detected'],0)
        self.assertEqual(result['survived'],3)

    def test_cli_strict_executes_valid_quoted_oracle(self):
        self.contract.write_text(self.text.replace('python -m unittest tests/test_app.py',
            'python -m unittest "tests/test_app.py"'),encoding='utf-8')
        result=subprocess.run([sys.executable,str(ROOT/'scripts/mutation_audit.py'),str(self.contract),
            '--repo-root',str(self.root),'--strict'],capture_output=True,text=True,encoding='utf-8',
            env=dict(os.environ,PYTHONUTF8='1'),timeout=45)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('3 detected',result.stdout)

    def test_unmatched_quotes_are_rejected_without_execution(self):
        with self.assertRaises(ValueError):audit._command('python "unterminated')
