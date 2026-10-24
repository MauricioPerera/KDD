"""Real Git, fresh interpreters, four trusted suite reports and build aborts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ('trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
           'validate_contracts.py', 'process_tree.py', 'execution_profile.py')
SOURCE = ('import os,unittest\nclass T(unittest.TestCase):\n'
          ' def id(self): return super().id()+os.environ.get("KDD_INVENTORY_FIXTURE_SUFFIX","")\n'
          ' def test_one(self): self.assertEqual(1+1,2)\n'
          ' def test_two(self): self.assertTrue(True)\n')
RUN_URL = 'https://github.com/MauricioPerera/KDD/actions/runs/41'


def digest(ids):
    return hashlib.sha256(('\n'.join(ids)+'\n').encode('utf-8')).hexdigest()


class PagesInventoryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        area = tempfile.TemporaryDirectory(prefix='kdd inventario CI \u00f1 ')
        cls.addClassCleanup(area.cleanup)
        cls.base = Path(area.name)
        cls.project = cls.base/'project with spaces'
        (cls.project/'scripts').mkdir(parents=True)
        (cls.project/'tests').mkdir()
        (cls.project/'site').mkdir()
        (cls.project/'knowledge').mkdir()
        (cls.project/'tests/test_core.py').write_text(SOURCE, encoding='utf-8')
        (cls.project/'knowledge/index.md').write_text('# Fixture\n', encoding='utf-8')
        cls.env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        cls.env.pop('PYTHONPATH', None)
        cls.env.pop('PYTHONHOME', None)
        cls.env.pop('KDD_INVENTORY_FIXTURE_SUFFIX', None)
        cls.env['PATH'] = str(Path(sys.executable).parent)+os.pathsep+cls.env.get('PATH','')
        for name in RUNTIME + ('mcp_gate_dispatch.py',):
            shutil.copyfile(ROOT/'scripts'/name, cls.project/'scripts'/name)
        for name in ('build.py', 'ci_inventory.py'):
            if (ROOT/'site'/name).is_file():
                shutil.copyfile(ROOT/'site'/name, cls.project/'site'/name)
        for name in ('index.html','support.html','assets/kdd-logo.svg','llms-skills.json',
                     'knowledge/index.html','knowledge/architecture/index.html',
                     'knowledge/contracts/index.html','knowledge/data_models/index.html'):
            target=cls.project/'site'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{}' if name.endswith('.json') else '<html>fixture</html>', encoding='utf-8')
        (cls.project/'site/index.html').write_text(
            ''.join('<span class="n" id="'+n+'">old</span>' for n in ('report-count','gate-count','test-count'))
            + '<a id="ci-evidence-link" href="old">CI</a>', encoding='utf-8')
        def run(argv, env=None):
            proc=subprocess.run(argv,cwd=cls.project,env=env or cls.env,capture_output=True,
                                text=True,encoding='utf-8',timeout=60)
            if proc.returncode:
                raise AssertionError(proc.stdout+proc.stderr)
            return proc
        run(['git','init','-q','-b','main'])
        for key,value in (('user.name','Pages integration'),('user.email','fixture@example.invalid'),
                          ('commit.gpgsign','false'),('core.autocrlf','false'),
                          ('maintenance.autoDetach','false'),('gc.autoDetach','false')):
            run(['git','config',key,value])
        run(['git','add','.']); run(['git','commit','-qm','Independent Pages fixture'])
        cls.sha=run(['git','rev-parse','HEAD']).stdout.strip()
        cls.bundle=cls.base/'bundle'
        run([sys.executable,'-I',str(cls.project/'scripts/trusted_ci.py'),'prepare',
             '--repo-root',str(cls.project),'--trusted-ref',cls.sha,'--bundle-dir',str(cls.bundle)])
        env=dict(cls.env,KDD_TRUSTED_BUNDLE=str(cls.bundle))
        cls.reports=[]
        for n in range(4):
            report=cls.base/('real-pass-'+str(n)+'.json')
            run([sys.executable,'-I',str(cls.bundle/'trusted_ci.py'),'suite',
                 '--repo-root',str(cls.project),'--start-directory','tests','--pattern','test_*.py',
                 '--workers','1','--report-json',str(report)],env)
            data=json.loads(report.read_text(encoding='utf-8'))
            if not data['ok'] or data['tests_run']!=2 or data['errors'] or data['failures']:
                raise AssertionError(data)
            cls.reports.append(report.read_bytes())
        cls.ids=data['expected_ids']

    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='kdd Pages caso ')
        self.addCleanup(temporary.cleanup)
        self.area=Path(temporary.name)
        self.repo=self.area/'project with spaces'
        self.env=dict(type(self).env)
        shutil.copytree(self.project,self.repo)

    def command(self,argv,cwd=None):
        return subprocess.run(argv,cwd=cwd or self.area,env=self.env,capture_output=True,
                              text=True,encoding='utf-8',timeout=60)

    def inspect(self,inventory=None,attempt=1,runtime=None):
        argv=[sys.executable,'-I',str(self.repo/'site/ci_inventory.py'),'inspect',
              '--repo-root',str(self.repo),'--ci-run-url',RUN_URL]
        if inventory is not None:
            argv+=['--ci-inventory-dir',str(inventory),'--ci-run-attempt',str(attempt),
                   '--ci-trusted-runtime-ref',runtime or self.sha]
        return self.command(argv)

    def exported(self,platform='ubuntu-latest',reports=None,output=None):
        source=self.area/('reports-'+platform)
        source.mkdir(exist_ok=True)
        offset=0 if platform=='ubuntu-latest' else 2
        payloads=self.reports[offset:offset+2] if reports is None else reports
        for n,content in enumerate(payloads):
            (source/('pass-'+str(n)+'.json')).write_bytes(content)
        target=output or self.area/'artifacts'/platform/'inventory.json'
        argv=[sys.executable,'-I',str(self.repo/'site/ci_inventory.py'),'export',
              '--repo-root',str(self.repo),'--reports-dir',str(source),'--output',str(target),
              '--run-id','41','--run-attempt','1','--head-sha',self.sha,
              '--platform',platform,'--trusted-runtime-ref',self.sha]
        return self.command(argv),target

    def manifests(self):
        paths=[]
        for platform in ('ubuntu-latest','windows-latest'):
            proc,path=self.exported(platform)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            paths.append(path)
        return self.area/'artifacts',paths

    def rejected(self,proc,kind):
        self.assertNotEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertIn(kind,proc.stdout+proc.stderr)

    def test_real_discovery_matches_executed_ids_in_real_passes(self):
        proc=self.inspect()
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        data=json.loads(proc.stdout)
        self.assertEqual(data['ids'],self.ids)
        self.assertEqual(data['tests'],2)
        self.assertEqual(data['ids_sha256'],digest(self.ids))
        self.assertEqual(data['inventory_source'],'discovery-preview')

    def test_import_error_cannot_be_counted_as_one_test(self):
        (self.repo/'tests/test_core.py').write_text('import kdd_missing_dependency_for_inventory\n'+SOURCE,encoding='utf-8')
        proc=self.inspect(); self.rejected(proc,'PAGES_DISCOVERY')
        self.assertIn('test_core',proc.stdout+proc.stderr)

    def test_syntax_error_aborts_discovery(self):
        (self.repo/'tests/test_core.py').write_text('def broken(:\n',encoding='utf-8')
        self.rejected(self.inspect(),'PAGES_DISCOVERY')

    def test_empty_discovery_is_rejected(self):
        (self.repo/'tests/test_core.py').unlink()
        self.rejected(self.inspect(),'PAGES_DISCOVERY')

    def test_duplicate_load_tests_ids_are_rejected(self):
        (self.repo/'tests/test_core.py').write_text(
            'import unittest\ndef load_tests(loader,tests,pattern):\n'
            ' case=unittest.FunctionTestCase(lambda:None)\n return unittest.TestSuite([case,case])\n',encoding='utf-8')
        self.rejected(self.inspect(),'PAGES_DISCOVERY')

    def test_load_tests_exception_aborts_discovery(self):
        (self.repo/'tests/test_core.py').write_text(
            SOURCE+'\ndef load_tests(loader,tests,pattern): raise RuntimeError("bad hook")\n',encoding='utf-8')
        self.rejected(self.inspect(),'PAGES_DISCOVERY')

    def test_discovery_does_not_execute_cases(self):
        (self.repo/'tests/test_core.py').write_text(
            'import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n'
            ' def test_must_not_run(self): Path("executed").touch();self.fail("not discovery")\n',encoding='utf-8')
        proc=self.inspect()
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['tests'],1)
        self.assertFalse((self.repo/'executed').exists())

    def test_export_binds_two_real_reports_to_commit_run_and_runtime(self):
        proc,path=self.exported()
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        data=json.loads(path.read_text(encoding='utf-8'))
        for key,value in {'schema_version':1,'repository':'MauricioPerera/KDD',
                          'workflow_path':'.github/workflows/validate.yml','run_id':41,
                          'run_attempt':1,'head_sha':self.sha,'platform':'ubuntu-latest',
                          'trusted_runtime_ref':self.sha,'ids':self.ids,'ids_sha256':digest(self.ids)}.items():
            self.assertEqual(data[key],value,key)
        self.assertEqual({p['report_sha256'] for p in data['passes']},
                         {hashlib.sha256(b).hexdigest() for b in self.reports[:2]})
        self.assertEqual([p['tests_run'] for p in data['passes']],[2,2])

    def test_export_rejects_corrupt_failed_or_incomplete_reports(self):
        original=json.loads(self.reports[0])
        changes=[{'ok':False},{'errors':[{'id':'test_core','traceback':'boom'}]},
                 {'executed_ids':self.ids[:1],'tests_run':1},
                 {'expected_ids':self.ids*2}, {'trusted_runtime_ref':'0'*40},
                 {'version':2}, {'tests_run':True}]
        for n,change in enumerate(changes):
            with self.subTest(change=change):
                data=dict(copy.deepcopy(original),**change)
                output=self.area/('bad-'+str(n)+'.json')
                proc,path=self.exported(reports=[json.dumps(data).encode(),self.reports[1]],output=output)
                self.rejected(proc,'PAGES_CI_INVENTORY')
                self.assertFalse(path.exists())

    def test_export_requires_two_distinct_complete_reports(self):
        for n,payloads in enumerate(([],self.reports[:1],self.reports[:3],self.reports[:1]*2,[b'not JSON',self.reports[1]])):
            with self.subTest(count=len(payloads)):
                # A fresh directory prevents leftovers from becoming inputs.
                source=self.area/'reports-ubuntu-latest'
                if source.exists():
                    for file in source.glob('*.json'): file.unlink()
                proc,path=self.exported(reports=payloads,output=self.area/('invalid-'+str(n)+'.json'))
                self.rejected(proc,'PAGES_CI_INVENTORY')
                self.assertFalse(path.exists())

    def test_export_rejects_two_valid_real_passes_with_different_ids(self):
        other=self.area/'other-real-pass.json'
        env=dict(self.env,KDD_TRUSTED_BUNDLE=str(self.bundle),KDD_INVENTORY_FIXTURE_SUFFIX='_different')
        proc=subprocess.run([sys.executable,'-I',str(self.bundle/'trusted_ci.py'),'suite',
                             '--repo-root',str(self.repo),'--start-directory','tests',
                             '--pattern','test_*.py','--workers','1','--report-json',str(other)],
                            cwd=self.area,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        data=json.loads(other.read_text(encoding='utf-8'))
        self.assertTrue(data['ok'])
        self.assertEqual(data['tests_run'],2)
        self.assertNotEqual(data['expected_ids'],self.ids)
        result,path=self.exported(reports=[self.reports[0],other.read_bytes()])
        self.rejected(result,'PAGES_CI_INVENTORY')
        self.assertFalse(path.exists())

    def test_public_counter_uses_consensus_of_four_real_passes(self):
        directory,_=self.manifests()
        proc=self.inspect(directory)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        data=json.loads(proc.stdout)
        self.assertEqual(data['tests'],2)
        self.assertEqual(data['ids'],self.ids)
        self.assertEqual(data['ids_sha256'],digest(self.ids))
        self.assertEqual(data['inventory_source'],'ci-verified')
        code=('import importlib.util,json,sys;from pathlib import Path;'
              's=importlib.util.spec_from_file_location("pages",sys.argv[1]);'
              'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
              'print(m.update_landing(Path(sys.argv[2]).read_text(),0,19,int(sys.argv[3]),sys.argv[4]))')
        html=self.command([sys.executable,'-I','-c',code,str(self.repo/'site/build.py'),
                           str(self.repo/'site/index.html'),str(data['tests']),RUN_URL])
        self.assertEqual(html.returncode,0,html.stderr)
        self.assertIn('id="test-count">2</span>',html.stdout)
        self.assertIn(RUN_URL,html.stdout)

    def test_reader_rejects_wrong_run_attempt_sha_repo_or_runtime(self):
        directory,paths=self.manifests()
        originals=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
        changes=[{'run_id':42},{'run_attempt':2},{'run_attempt':True},{'head_sha':'0'*40},
                 {'repository':'Other/Repo'},{'workflow_path':'.github/workflows/other.yml'},
                 {'trusted_runtime_ref':'0'*40},{'schema_version':2}]
        for change in changes:
            with self.subTest(change=change):
                for path,data in zip(paths,originals):
                    path.write_text(json.dumps(dict(copy.deepcopy(data),**change)),encoding='utf-8')
                self.rejected(self.inspect(directory),'PAGES_CI_INVENTORY')

    def test_reader_rejects_disagreeing_ids_bad_digest_and_replayed_pass(self):
        directory,paths=self.manifests()
        original=json.loads(paths[1].read_text(encoding='utf-8'))
        other=sorted([self.ids[0],'test_core.T.test_wrong'])
        changes=[{'ids':other,'ids_sha256':digest(other)}, {'ids_sha256':'0'*64},
                 {'ids':self.ids*2}, {'ids':[]}, {'platform':'ubuntu-latest'},
                 {'passes':original['passes'][:1]},
                 {'passes':original['passes'][:1]*2},
                 {'passes':json.loads(paths[0].read_text(encoding='utf-8'))['passes']},
                 {'passes':[dict(original['passes'][0],duration_seconds=float('nan')),original['passes'][1]]}]
        for change in changes:
            with self.subTest(change=change):
                paths[1].write_text(json.dumps(dict(copy.deepcopy(original),**change)),encoding='utf-8')
                self.rejected(self.inspect(directory),'PAGES_CI_INVENTORY')
        paths[1].write_text('not JSON',encoding='utf-8')
        self.rejected(self.inspect(directory),'PAGES_CI_INVENTORY')

    def test_reader_rejects_local_discovery_mismatch(self):
        directory,_=self.manifests()
        with self.subTest(condition='same commit and count, different IDs'):
            self.env['KDD_INVENTORY_FIXTURE_SUFFIX']='_different'
            self.rejected(self.inspect(directory),'PAGES_CI_INVENTORY')
            del self.env['KDD_INVENTORY_FIXTURE_SUFFIX']
        with self.subTest(condition='same IDs but changed tracked public source'):
            (self.repo/'knowledge/index.md').write_text('# Different public content\n',encoding='utf-8')
            preview=self.inspect()
            self.assertEqual(preview.returncode,0,preview.stdout+preview.stderr)
            self.assertEqual(json.loads(preview.stdout)['ids'],self.ids)
            self.rejected(self.inspect(directory),'PAGES_CI_INVENTORY')

    def build_error(self,source,inventory=False):
        (self.repo/'tests/test_core.py').write_text(source,encoding='utf-8')
        output=self.area/'public-bundle'
        argv=[sys.executable,'-I',str(self.repo/'site/build.py'),'--output',str(output),'--ci-run-url',RUN_URL]
        if inventory:
            directory,paths=self.manifests()
            data=json.loads(paths[0].read_text(encoding='utf-8'));data['run_id']=42
            paths[0].write_text(json.dumps(data),encoding='utf-8')
            argv+=['--ci-inventory-dir',str(directory),'--ci-run-attempt','1',
                   '--ci-trusted-runtime-ref',self.sha]
        proc=self.command(argv)
        self.rejected(proc,'PAGES_CI_INVENTORY' if inventory else 'PAGES_DISCOVERY')
        self.assertFalse(output.exists(),proc.stdout+proc.stderr)
        self.assertNotIn('Run npm ci',proc.stderr)

    def test_real_build_aborts_before_output_on_import_error(self):
        self.build_error('import kdd_missing_dependency_for_inventory\n'+SOURCE)

    def test_real_build_aborts_before_output_on_syntax_error(self):
        self.build_error('def syntax_error(:\n')

    def test_real_build_rejects_invalid_ci_identity_before_output(self):
        self.build_error(SOURCE,inventory=True)

    def test_missing_ci_evidence_does_not_fall_back_to_preview(self):
        directory=self.area/'empty-artifacts';directory.mkdir()
        self.rejected(self.inspect(directory),'PAGES_CI_INVENTORY')


if __name__=='__main__':
    unittest.main()
