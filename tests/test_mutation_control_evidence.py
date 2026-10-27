"""Real controls distinguish a broken experiment from a detected mutant."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mutation_audit as audit

TARGET='def accept(value):\n if value == 1:\n  return True\n return False\n'
STRONG='import unittest\nfrom src.app import accept\nclass TestApp(unittest.TestCase):\n def test_value(self):\n  self.assertTrue(accept(1))\n  self.assertFalse(accept(2))\n'

class MutationControls(unittest.TestCase):
    def project(self,oracle=STRONG):
        area=tempfile.TemporaryDirectory(prefix='kdd-mutation-controls-')
        self.addCleanup(area.cleanup)
        root=Path(area.name)/'project';root.mkdir()
        for name in ['src','tests','knowledge/contracts']:(root/name).mkdir(parents=True,exist_ok=True)
        (root/'src/__init__.py').write_text('',encoding='utf-8')
        (root/'tests/__init__.py').write_text('',encoding='utf-8')
        (root/'src/app.py').write_text(TARGET,encoding='utf-8')
        (root/'tests/test_app.py').write_text(oracle,encoding='utf-8')
        contract=root/'knowledge/contracts/app.md'
        text="""---
type: 'Task Contract'
title: 'Mutation control fixture'
description: 'Actual oracle for a controlled mutation experiment.'
tags: ['test']
task: mutation-control-fixture
intent: 'Verify the fixture target.'
target: src/app.py
signature: 'def accept(value):'
test_command: 'python -m unittest tests/test_app.py'
budget:
  cyclomatic_max: 4
  nesting_max: 3
tests: tests/test_app.py
tests_sha256: 'DIGEST'
touch_only: ['src/app.py']
deps_allowed: ['stdlib']
forbids: ['network']
---
## Intent
Verify input classification.
## Interface
accept(value).
## Invariants
- True only for one.
## Examples
- one passes; two fails.
- Original tests are retained.
## Do / Don't
- DO run real tests.
## Tests
tests/test_app.py.
## Constraints
PARAR y reportar si se requiere red.
"""
        contract.write_text(text.replace('DIGEST',hashlib.sha256(oracle.encode()).hexdigest()),encoding='utf-8')
        return root,contract,Path(area.name)

    def controls(self,result,statuses):
        controls=result.get('controls')
        self.assertIsInstance(controls,list,'the report must retain actual original/copy controls')
        self.assertEqual([item['stage'] for item in controls],['original','copy'][:len(statuses)])
        self.assertEqual([item['status'] for item in controls],statuses)
        return controls

    def test_broken_original_import_rejects_before_mutants(self):
        root,contract,_=self.project('import missing_mutation_control_dependency\n')
        result=audit.audit_contract(str(contract),str(root),timeout=5)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['detected'],0)
        self.assertEqual(result['mutants'],[])
        self.controls(result,['INCONCLUSIVE'])

    def test_agents_helper_is_preserved_and_uncovered_mutants_survive(self):
        oracle="import sys,unittest\nfrom pathlib import Path\nsys.path.insert(0,str(Path.cwd()/'.agents/helpers'))\nfrom support import expected\nclass TestApp(unittest.TestCase):\n def test_fixture(self):self.assertEqual(expected,7)\n"
        root,contract,_=self.project(oracle)
        helper=root/'.agents/helpers/support.py';helper.parent.mkdir(parents=True)
        helper.write_text('expected=7\n',encoding='utf-8')
        result=audit.audit_contract(str(contract),str(root),timeout=5)
        self.assertEqual(result['detected'],0)
        self.assertEqual(result['survived'],3)
        self.assertEqual(result['status'],'FAIL')
        self.controls(result,['PASS','PASS'])

    def test_agents_logs_are_regenerable_but_other_agents_inputs_are_copied(self):
        oracle="import unittest\nfrom pathlib import Path\nclass TestApp(unittest.TestCase):\n def test_inputs(self):\n  self.assertEqual(Path('.agents/data.txt').read_text(),'fixture')\n  self.assertFalse(Path('.agents/logs/old.txt').exists())\n"
        root,contract,_=self.project(oracle)
        (root/'.agents/logs').mkdir(parents=True)
        (root/'.agents/data.txt').write_text('fixture',encoding='utf-8')
        (root/'.agents/logs/old.txt').write_text('regenerable',encoding='utf-8')
        result=audit.audit_contract(str(contract),str(root),timeout=5)
        self.assertEqual(result['survived'],3)
        self.assertEqual(result['detected'],0)
        self.controls(result,['PASS','PASS'])

    def test_real_strong_oracle_detects_all_three_mutants_after_controls(self):
        root,contract,_=self.project()
        result=audit.audit_contract(str(contract),str(root),timeout=5)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['detected'],3)
        self.assertEqual(result['survived'],0)
        controls=self.controls(result,['PASS','PASS'])
        self.assertTrue(all(item['exit_code']==0 for item in controls))

    def test_oracles_never_execute_inside_the_original_working_tree(self):
        oracle="from pathlib import Path\nPath('execution.marker').write_text('ran')\n"+STRONG
        root,contract,_=self.project(oracle)
        before={name:(root/name).read_bytes() for name in ['src/app.py','tests/test_app.py','knowledge/contracts/app.md']}
        result=audit.audit_contract(str(contract),str(root),timeout=5)
        self.assertEqual(result['detected'],3)
        self.assertFalse((root/'execution.marker').exists())
        self.assertEqual({name:(root/name).read_bytes() for name in before},before)
        self.controls(result,['PASS','PASS'])

    def test_original_timeout_is_inconclusive_without_any_mutant(self):
        root,contract,_=self.project('import time\ntime.sleep(8)\n'+STRONG)
        result=audit.audit_contract(str(contract),str(root),timeout=0.5)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['detected'],0)
        self.assertEqual(result['mutants'],[])
        controls=self.controls(result,['INCONCLUSIVE'])
        self.assertTrue(controls[0]['timeout'])

    def counted(self,fail_second=False,mutant_timeout=False):
        root,contract,area=self.project()
        counter=area/'actual-invocations.txt'
        prefix=f"from pathlib import Path\np=Path({str(counter)!r})\ncalls=len(p.read_text().splitlines()) if p.exists() else 0\nwith p.open('a') as stream:stream.write('run\\n')\n"
        if fail_second:prefix+="if calls==1:raise ImportError('copy control unavailable')\n"
        if mutant_timeout:prefix+="if calls>=2:\n import time\n time.sleep(8)\n"
        # This oracle intentionally does not exercise the target.
        oracle=prefix+"import unittest\nclass TestApp(unittest.TestCase):\n def test_fixture(self):self.assertTrue(True)\n"
        (root/'tests/test_app.py').write_text(oracle,encoding='utf-8')
        text=contract.read_text(encoding='utf-8').replace(hashlib.sha256(STRONG.encode()).hexdigest(),hashlib.sha256(oracle.encode()).hexdigest())
        contract.write_text(text,encoding='utf-8')
        return root,contract,counter

    def test_failing_copy_control_is_not_a_detected_mutant(self):
        root,contract,counter=self.counted(fail_second=True)
        result=audit.audit_contract(str(contract),str(root),timeout=5)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['detected'],0)
        self.assertEqual(result['mutants'],[])
        self.assertEqual(len(counter.read_text().splitlines()),2)
        self.controls(result,['PASS','INCONCLUSIVE'])

    def test_mutant_timeouts_after_green_controls_remain_inconclusive(self):
        root,contract,_=self.counted(mutant_timeout=True)
        result=audit.audit_contract(str(contract),str(root),timeout=2)
        self.assertEqual(result['detected'],0)
        self.assertEqual(result['inconclusive'],3)
        self.assertEqual(result['survived'],0)
        self.controls(result,['PASS','PASS'])

    def test_strict_cli_rejects_a_broken_baseline(self):
        root,contract,_=self.project('import missing_mutation_control_dependency\n')
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/mutation_audit.py'),str(contract),
            '--repo-root',str(root),'--strict'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertNotEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertIn('original',proc.stdout.lower())

    def test_no_applicable_operator_still_skips_explicitly(self):
        root,contract,_=self.project()
        (root/'src/app.py').write_text('def accept(value):\n return value\n',encoding='utf-8')
        result=audit.audit_contract(str(contract),str(root),timeout=5)
        self.assertEqual(result['status'],'SKIP')
        self.assertEqual(result['mutants'],[])

if __name__=='__main__':unittest.main()
