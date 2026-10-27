"""Native defaults plus real six-process barriers, fixtures and fresh reports."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
COMMAND='run: python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . --start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" --report-dir "$RUNNER_TEMP/kdd-suite-reports"'
RUNTIME=('trusted_ci.py','run_test_suite.py','validate_test_commands.py','validate_contracts.py','process_tree.py','execution_profile.py')


def selected(name,platform='windows-latest',repository='MauricioPerera/KDD',reusable=False,explicit=''):
    """Read the workflow and evaluate only its documented boolean/string subset."""
    text=(ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8')
    line=next(line.strip() for line in text.splitlines() if line.strip().startswith('KDD_'+name.upper()+'_WORKERS:'))
    expression=line.split('${{',1)[1].rsplit('}}',1)[0].strip()
    expression=re.sub(r'!(?!=)','not ',expression.replace('&&',' and ').replace('||',' or ')).strip()
    values={'inputs':{'suite_workers':explicit if name=='suite' else '',
                      'contract_workers':explicit if name=='contract' else '',
                      'reusable_execution':reusable},
            'github':{'repository':repository},'matrix':{'os':platform}}
    def evaluate(node):
        if isinstance(node,ast.Constant) and isinstance(node.value,(str,bool)):return node.value
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name):return values[node.value.id][node.attr]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):return not evaluate(node.operand)
        if isinstance(node,ast.Compare) and len(node.ops)==1 and isinstance(node.ops[0],ast.Eq):
            left,right=evaluate(node.left),evaluate(node.comparators[0])
            if isinstance(left,str) and isinstance(right,str):return left.casefold()==right.casefold()
            return left==right
        if isinstance(node,ast.BoolOp):
            result=evaluate(node.values[0])
            for item in node.values[1:]:
                if isinstance(node.op,ast.And):result=evaluate(item) if result else result
                elif isinstance(node.op,ast.Or):result=result if result else evaluate(item)
                else:raise AssertionError('unsupported workflow operator')
            return result
        raise AssertionError('unsupported workflow expression node: '+ast.dump(node))
    return evaluate(ast.parse(expression,mode='eval').body)


class WorkflowProfile(unittest.TestCase):
    def test_native_windows_suite_default_is_six(self):
        self.assertEqual(selected('suite'),'6')

    def test_native_ubuntu_suite_default_remains_four(self):
        self.assertEqual(selected('suite',platform='ubuntu-latest'),'4')

    def test_contract_pool_and_exclusive_bootstrap_keep_their_limits(self):
        for platform in ('windows-latest','ubuntu-latest'):
            self.assertEqual(selected('contract',platform=platform),'4')
        text=(ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertIn('--timeout 600 --deduplicate --workers "$KDD_CONTRACT_WORKERS"',text)
        self.assertIn('--exclusive-commands-json "$KDD_EXCLUSIVE_CONTRACT_COMMANDS"',text)
        self.assertIn('python -m unittest tests/test_init_project.py',text)

    def test_reusable_and_external_repository_defaults_remain_serial(self):
        for kind in ('suite','contract'):
            for platform in ('windows-latest','ubuntu-latest'):
                self.assertEqual(selected(kind,platform=platform,reusable=True),'1')
                self.assertEqual(selected(kind,platform=platform,repository='example/new-project'),'1')

    def test_explicit_worker_inputs_precede_native_defaults(self):
        for kind in ('suite','contract'):
            for platform in ('windows-latest','ubuntu-latest'):
                self.assertEqual(selected(kind,platform=platform,explicit='3'),'3')
                self.assertEqual(selected(kind,platform=platform,reusable=True,explicit='2'),'2')
        self.assertEqual(selected('suite',explicit='0'),'0')

    def test_dual_os_and_two_identical_consecutive_commands_remain(self):
        text=(ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertEqual(text.count('os: [ubuntu-latest, windows-latest]'),2)
        self.assertEqual(text.count(COMMAND),2)
        first=text.index('- name: Run unit tests (1/2)');second=text.index('- name: Run unit tests (2/2)')
        self.assertLess(first,second)
        between=text[first:second]
        self.assertEqual(between.count('- name:'),1)
        for number in (1,2):
            block=text.split('- name: Run unit tests ('+str(number)+'/2)',1)[1].split('\n      - ',1)[0]
            self.assertIn(COMMAND,block)
            self.assertIn("KDD_SKIP_INIT_POST_APPLY_SUITE: '1'",block)
        self.assertNotIn('continue-on-error:',text)


class SixWorkerIntegration(unittest.TestCase):
    def setUp(self):
        area=tempfile.TemporaryDirectory(prefix='kdd six workers \u00f1 ')
        self.addCleanup(area.cleanup);self.area=Path(area.name).resolve()
        self.root=self.area/'project';(self.root/'scripts').mkdir(parents=True)
        (self.root/'tests').mkdir();(self.root/'events').mkdir()
        for name in RUNTIME:shutil.copyfile(ROOT/'scripts'/name,self.root/'scripts'/name)
        from tests.test_fixture_preparation import configure_git
        self.command(['git','init','-q','-b','main'])
        configure_git(self.root,{'user.name':'Synthetic profile reviewer','user.email':'fixture@example.invalid',
            'core.autocrlf':'false','commit.gpgsign':'false','maintenance.autoDetach':'false','gc.autoDetach':'false'})
        self.command(['git','add','scripts']);self.command(['git','commit','-qm','Synthetic runtime fixture only; no real approval'])
        self.ref=self.command(['git','rev-parse','HEAD']).stdout.strip()
        self.bundle=self.area/'bundle';self.reports=self.area/'reports'
        self.command([sys.executable,'-I',str(self.root/'scripts/trusted_ci.py'),'prepare','--repo-root',str(self.root),
            '--trusted-ref',self.ref,'--bundle-dir',str(self.bundle)])
        self.epoch=0

    def command(self,argv,expected=0):
        result=subprocess.run(argv,cwd=self.root,capture_output=True,text=True,encoding='utf-8',
            env=dict(os.environ,PYTHONUTF8='1'),timeout=60)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return result

    def modules(self,fail=False):
        for number in range(6):
            code='''import json,os,time,unittest
from pathlib import Path
ROOT=Path.cwd()
INDEX=NUMBER
def record(kind):
 epoch=json.loads((ROOT/'epoch.json').read_text())['epoch']
 file=ROOT/'events'/(str(epoch)+'-'+str(INDEX)+'.'+kind)
 with file.open('a',encoding='utf-8') as stream:stream.write(str(os.getpid())+'\\n')
def setUpModule():record('module')
class Lane(unittest.TestCase):
 @classmethod
 def setUpClass(cls):record('class')
 def test_barrier(self):
  epoch=json.loads((ROOT/'epoch.json').read_text())['epoch']
  begin=time.monotonic()
  (ROOT/'events'/(str(epoch)+'-'+str(INDEX)+'.ready')).write_text(json.dumps({'pid':os.getpid(),'start':begin}),encoding='utf-8')
  deadline=begin+10
  while len(list((ROOT/'events').glob(str(epoch)+'-*.ready')))!=6 and time.monotonic()<deadline:time.sleep(.01)
  self.assertEqual(len(list((ROOT/'events').glob(str(epoch)+'-*.ready'))),6,'all six processes must reach the real barrier')
  if BROKEN and INDEX==0:self.assertEqual(1,2,'genuine worker failure')
  (ROOT/'events'/(str(epoch)+'-'+str(INDEX)+'.end')).write_text(str(time.monotonic()),encoding='utf-8')
'''.replace('NUMBER',str(number)).replace('BROKEN',repr(fail))
            (self.root/'tests'/('test_lane_'+str(number)+'.py')).write_text(code,encoding='utf-8')

    def execute(self,workers):
        self.epoch+=1;(self.root/'epoch.json').write_text(json.dumps({'epoch':self.epoch}),encoding='utf-8')
        before=set(self.reports.glob('*.json')) if self.reports.exists() else set()
        argv=[sys.executable,'-I',str(self.bundle/'trusted_ci.py'),'suite','--repo-root',str(self.root),
            '--start-directory','tests','--pattern','test_*.py','--workers',str(workers),'--report-dir',str(self.reports)]
        result=subprocess.run(argv,cwd=self.root,capture_output=True,text=True,encoding='utf-8',timeout=60,
            env=dict(os.environ,PYTHONUTF8='1',KDD_TRUSTED_BUNDLE=str(self.bundle)))
        created=set(self.reports.glob('*.json'))-before
        self.assertEqual(len(created),1,result.stdout+result.stderr)
        file=created.pop();data=json.loads(file.read_text(encoding='utf-8'))
        return result,data,file,argv

    def successful(self,result,data):
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(data['ok'])
        self.assertEqual(data['workers'],6)
        self.assertEqual(data['tests_run'],6)
        self.assertEqual(data['expected_ids'],['test_lane_'+str(n)+'.Lane.test_barrier' for n in range(6)])
        self.assertEqual(data['expected_ids'],data['executed_ids'])
        self.assertEqual(len(set(data['executed_ids'])),6)
        self.assertEqual(data['skipped'],[])
        self.assertEqual(data['fixture_omitted_ids'],[])
        ready=[json.loads((self.root/'events'/(str(self.epoch)+'-'+str(n)+'.ready')).read_text()) for n in range(6)]
        ends=[float((self.root/'events'/(str(self.epoch)+'-'+str(n)+'.end')).read_text()) for n in range(6)]
        self.assertEqual(len({r['pid'] for r in ready}),6)
        self.assertLessEqual(max(r['start'] for r in ready),min(ends))
        for number in range(6):
            for kind in ('module','class'):
                records=(self.root/'events'/(str(self.epoch)+'-'+str(number)+'.'+kind)).read_text().splitlines()
                self.assertEqual(len(records),1)
                self.assertEqual(int(records[0]),ready[number]['pid'])

    def test_selected_windows_default_reaches_six_real_processes(self):
        self.modules();result,data,_file,_argv=self.execute(selected('suite'))
        self.successful(result,data)

    def test_explicit_six_runs_twice_with_fresh_reports_and_fixtures(self):
        self.modules();runs=[self.execute('6'),self.execute('6')]
        for epoch,(result,data,_file,_argv) in enumerate(runs,1):
            self.epoch=epoch;self.successful(result,data)
        self.assertEqual(runs[0][3],runs[1][3])
        self.assertNotEqual(runs[0][2],runs[1][2])
        self.assertNotEqual(hashlib.sha256(runs[0][2].read_bytes()).hexdigest(),hashlib.sha256(runs[1][2].read_bytes()).hexdigest())

    def test_six_worker_real_failure_keeps_nonzero_exit_and_all_ids(self):
        self.modules(fail=True);result,data,_file,_argv=self.execute('6')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(data['ok']);self.assertEqual(data['tests_run'],6)
        self.assertEqual(data['expected_ids'],data['executed_ids'])
        self.assertEqual(len(data['failures']),1)
        summaries=[json.loads(line.split('KDD_SUITE_REPORT ',1)[1]) for line in result.stdout.splitlines()
                   if line.startswith('KDD_SUITE_REPORT ')]
        self.assertEqual(len(summaries),1)
        self.assertEqual(summaries[0]['failures'],1);self.assertEqual(summaries[0]['errors'],0)
        self.assertTrue(all(entry['id']=='runner' for entry in data['errors']))
        self.assertIn('genuine worker failure',str(data['failures']))
        self.assertEqual(data['skipped'],[]);self.assertEqual(data['fixture_omitted_ids'],[])

    def test_invalid_explicit_worker_input_never_executes_a_case(self):
        self.modules();value=selected('suite',explicit='0')
        self.assertEqual(value,'0')
        result=subprocess.run([sys.executable,'-I',str(self.bundle/'trusted_ci.py'),'suite','--repo-root',str(self.root),
            '--start-directory','tests','--pattern','test_*.py','--workers',value,'--report-dir',str(self.reports)],
            cwd=self.root,capture_output=True,text=True,encoding='utf-8',timeout=60,
            env=dict(os.environ,PYTHONUTF8='1',KDD_TRUSTED_BUNDLE=str(self.bundle)))
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(list((self.root/'events').iterdir()),[])


class InitializedProfile(unittest.TestCase):
    def test_initialized_source_without_git_executes_profile_and_real_controls(self):
        from tests import test_init_project as support
        area=tempfile.TemporaryDirectory(prefix='kdd initialized six profile ');self.addCleanup(area.cleanup)
        project=Path(area.name)/'project';support._copy_repo(str(project),full=True)
        complete=all((project/name).exists() for name in support.MANIFEST)
        self.assertEqual(complete,all((ROOT/name).exists() for name in support.MANIFEST))
        if complete:
            applied=subprocess.run([sys.executable,'-X','utf8',str(project/'scripts/init_project.py'),'--apply','--repository','ExampleCo/SixProfile'],cwd=project,
                capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(applied.returncode,0,applied.stdout+applied.stderr)
            self.assertFalse(any((project/name).exists() for name in support.MANIFEST))
        self.assertFalse((project/'.git').exists())
        result=subprocess.run([sys.executable,'-X','utf8','-m','unittest',
            'tests.test_ci_windows_suite_profile.WorkflowProfile','tests.test_ci_windows_suite_profile.SixWorkerIntegration'],
            cwd=project,capture_output=True,text=True,encoding='utf-8',timeout=180,
            env=dict(os.environ,PYTHONUTF8='1'))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertRegex(result.stderr,r'Ran 10 tests?')
        self.assertNotIn('skipped=',result.stderr)


if __name__=='__main__':unittest.main()
