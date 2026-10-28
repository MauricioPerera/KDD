"""Real contracts, Git preimages and aliases confine all mutant writes."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from tests import test_mutation_control_evidence as support
from tests.test_fixture_preparation import configure_git, directory_alias

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mutation_audit as audit
from validate_contracts import validate_file


class MutationTargetBoundary(unittest.TestCase):
    def setUp(self):
        fixture=support.MutationControls('test_broken_original_import_rejects_before_mutants')
        self.addCleanup(fixture.doCleanups)
        self.root,self.contract,self.area=fixture.project()
        self.root=self.root.resolve();self.area=self.area.resolve()
        self.text=self.contract.read_text(encoding='utf-8')
        self.env=dict(os.environ,PYTHONUTF8='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1')
        subprocess.run(['git','init','-q','-b','main',str(self.root)],check=True,capture_output=True,env=self.env)
        configure_git(self.root,{'user.name':'Mutation fixture','user.email':'fixture@example.invalid',
            'maintenance.autoDetach':'false','gc.autoDetach':'false','core.autocrlf':'false','commit.gpgsign':'false'})
        self.git('add','-A');self.git('commit','-qm','Own fixture baseline')

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],env=self.env,timeout=30)

    def retarget(self,target):
        self.contract.write_text(self.text.replace('target: src/app.py',"target: '"+target+"'")
            .replace("touch_only: ['src/app.py']","touch_only: ['"+target+"']"),encoding='utf-8')

    def snapshot(self):
        return {'source':(self.root/'src/app.py').read_bytes(),
            'oracle':(self.root/'tests/test_app.py').read_bytes(),
            'index':hashlib.sha256((self.root/'.git/index').read_bytes()).hexdigest(),
            'head':(self.root/'.git/HEAD').read_bytes(),
            'refs':self.git('for-each-ref','--format=%(refname) %(objectname)')}

    def result(self):
        try:return audit.audit_contract(str(self.contract),str(self.root),timeout=10)
        except Exception as error:self.fail('Unsafe input must produce structured REJECT: '+repr(error))

    def rejected(self):
        before=self.snapshot()
        result=self.result()
        self.assertEqual(result['status'],'REJECT','unsafe target must be rejected before controls/copy')
        self.assertEqual(result['detected'],0);self.assertEqual(result['mutants'],[])
        self.assertFalse(result.get('controls',[]))
        self.assertEqual(self.snapshot(),before)

    def test_relative_target_keeps_original_and_runs_real_mutants(self):
        before=self.snapshot();result=self.result()
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['detected'],3)
        self.assertEqual([c['status'] for c in result['controls']],['PASS','PASS'])
        self.assertEqual(self.snapshot(),before)

    def test_absolute_target_inside_project_rejected_before_writing(self):
        self.retarget((self.root/'src/app.py').as_posix());self.rejected()

    def test_absolute_external_target_preserves_canary(self):
        outside=self.area/'outside.py';outside.write_text(support.TARGET,encoding='utf-8')
        before=outside.read_bytes();self.retarget(outside.as_posix());self.rejected()
        self.assertEqual(outside.read_bytes(),before)

    def test_relative_parent_escape_preserves_canary(self):
        outside=self.area/'outside.py';outside.write_text(support.TARGET,encoding='utf-8')
        before=outside.read_bytes();self.retarget('../outside.py');self.rejected()
        self.assertEqual(outside.read_bytes(),before)

    def test_noncanonical_traversal_inside_root_is_rejected(self):
        self.retarget('src/../src/app.py');self.rejected()

    def test_external_directory_alias_is_rejected(self):
        source=self.root/'src';outside=self.area/'external-src';source.rename(outside)
        directory_alias(source,outside,self.area);self.addCleanup(self.remove_alias,source)
        self.rejected()

    def test_internal_directory_alias_is_rejected(self):
        source=self.root/'src';outside=self.root/'alternate-src';source.rename(outside)
        directory_alias(source,outside,self.area);self.addCleanup(self.remove_alias,source)
        self.rejected()

    @staticmethod
    def remove_alias(path):
        if path.is_symlink():path.unlink()
        else:path.rmdir()

    def test_hardlinked_target_preserves_external_canary(self):
        outside=self.area/'external-hardlink.py';os.link(self.root/'src/app.py',outside)
        before=outside.read_bytes();self.rejected();self.assertEqual(outside.read_bytes(),before)

    def test_foreign_non_python_paths_reject_before_skip_or_network(self):
        for value in ['C:outside.ts','Z:/outside.ts','//unreachable.invalid/share/outside.ts',
                      '\\\\unreachable.invalid\\share\\outside.ts']:
            with self.subTest(value=value):self.retarget(value);self.rejected()

    def cli(self,strict):
        args=[sys.executable,str(ROOT/'scripts/mutation_audit.py'),str(self.contract),'--repo-root',str(self.root)]
        if strict:args.append('--strict')
        return subprocess.run(args,capture_output=True,text=True,encoding='utf-8',env=self.env,timeout=45)

    def test_cli_without_strict_rejects_unsafe_target(self):
        self.retarget((self.root/'src/app.py').as_posix());before=self.snapshot();result=self.cli(False)
        self.assertNotEqual(result.returncode,0);self.assertIn('REJECT',result.stdout+result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_cli_strict_rejects_before_controls_or_mutation(self):
        self.retarget((self.root/'src/app.py').as_posix());before=self.snapshot();result=self.cli(True)
        self.assertNotEqual(result.returncode,0);self.assertIn('REJECT',result.stdout+result.stderr)
        self.assertEqual(self.snapshot(),before)

    def test_contract_validator_rejects_absolute_target(self):
        self.retarget((self.root/'src/app.py').as_posix())
        findings=validate_file(str(self.contract),repo_root=str(self.root))
        self.assertTrue(any(f.level=='ERROR' and 'target' in str(f).lower() for f in findings))

    def test_contract_validator_rejects_absolute_oracle(self):
        value=(self.root/'tests/test_app.py').as_posix()
        self.contract.write_text(self.text.replace('tests: tests/test_app.py',"tests: '"+value+"'"),encoding='utf-8')
        findings=validate_file(str(self.contract),repo_root=str(self.root))
        self.assertTrue(any(f.level=='ERROR' and 'tests' in str(f).lower() for f in findings))

    def test_contract_validator_rejects_noncanonical_target(self):
        self.retarget('src/../src/app.py')
        findings=validate_file(str(self.contract),repo_root=str(self.root))
        self.assertTrue(any(f.level=='ERROR' and 'target' in str(f).lower() for f in findings))

    def test_contract_validator_keeps_regular_relative_paths(self):
        self.assertFalse([f for f in validate_file(str(self.contract),repo_root=str(self.root)) if f.level=='ERROR'])

    def test_regular_non_python_target_still_skips_explicitly(self):
        (self.root/'src/app.ts').write_text('export const value=7;\n',encoding='utf-8')
        self.retarget('src/app.ts');result=self.result()
        self.assertEqual(result['status'],'SKIP');self.assertEqual(result['mutants'],[])

    def test_regular_python_without_operator_still_skips_explicitly(self):
        (self.root/'src/app.py').write_text('def accept(value):\n return value\n',encoding='utf-8')
        result=self.result();self.assertEqual(result['status'],'SKIP');self.assertEqual(result['mutants'],[])
