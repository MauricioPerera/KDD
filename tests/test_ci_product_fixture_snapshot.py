"""Real Git/quality controls for bounded product fixture preparation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

PROBE=r'''
import ctypes,json,os,sys,traceback
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import tests.test_approval_routing as routing
source=Path(sys.argv[2]);work=Path(sys.argv[3]);mode=sys.argv[4]
routing.ROOT=source
case=routing.TestApprovalRouting('test_guard_accepts_two_real_pr_merges_without_changing_main')
kind=type(case);kind.root=work;kind._product_cache=None
events=[];changed_during_preparation=False
def arguments(value):
 if not isinstance(value,str):return list(value)
 count=ctypes.c_int();shell=ctypes.WinDLL('shell32');kernel=ctypes.WinDLL('kernel32')
 shell.CommandLineToArgvW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
 shell.CommandLineToArgvW.restype=ctypes.POINTER(ctypes.c_wchar_p)
 kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
 pointer=shell.CommandLineToArgvW(value,ctypes.byref(count))
 try:return [pointer[i] for i in range(count.value)]
 finally:kernel.LocalFree(ctypes.cast(pointer,ctypes.c_void_p))
def observed(event,data):
 global changed_during_preparation
 if event=='subprocess.Popen':
  argv=arguments(data[1]);cwd=data[2]
  clone='clone' in argv and Path(argv[-1]).name=='product'
  if clone or (cwd and Path(cwd).name=='product'):events.append(argv)
  if mode=='during' and not changed_during_preparation and cwd and Path(cwd).name=='product' and 'init' in argv:
   (source/'fixture-source.txt').write_text('two',encoding='utf-8');changed_during_preparation=True
sys.addaudithook(observed)
report=dict(error=None,error_type=None,mode=mode)
def fresh(name):
 area=work/name;area.mkdir();return case.fresh_product(area)
def git(project,*args):return case.command('git',*args,cwd=project)
try:
 if mode=='partial':
  from scripts.init_project import MANIFEST
  item=source/MANIFEST[0];item.parent.mkdir(parents=True,exist_ok=True);item.write_text('partial',encoding='utf-8')
  fresh('partial')
 elif mode=='during':
  (source/'fixture-source.txt').write_text('one',encoding='utf-8');fresh('during')
 elif mode=='changed':
  note=source/'fixture-source.txt';note.write_text('one',encoding='utf-8');stamp=note.stat()
  first,one,tree_one=fresh('one')
  note.write_text('two',encoding='utf-8');os.utime(note,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
  second,two,tree_two=fresh('two')
  report.update(notes=[(p/'fixture-source.txt').read_text(encoding='utf-8') for p in (first,second)],
   refs_changed=one!=two,trees_changed=tree_one!=tree_two,same_size=note.stat().st_size==stamp.st_size,
   same_mtime=note.stat().st_mtime_ns==stamp.st_mtime_ns)
 else:
  first,approved,tree=fresh('one');second,two,tree_two=fresh('two')
  (first/'src/product.py').write_text("raise RuntimeError('mutated isolated clone')\n",encoding='utf-8')
  git(first,'branch','private-one')
  third,three,tree_three=fresh('three')
  projects=(first,second,third)
  policy=['--policy','quality/product.json','--approved-ref',approved]
  positive=__import__('subprocess').run([sys.executable,'scripts/verify_quality.py',*policy],cwd=second,capture_output=True,text=True,encoding='utf-8',timeout=60)
  negative=__import__('subprocess').run([sys.executable,'scripts/verify_quality.py',*policy],cwd=first,capture_output=True,text=True,encoding='utf-8',timeout=60)
  report.update(same_refs=approved==two==three,same_trees=tree==tree_two==tree_three,
   own_git_dirs=len({git(p,'rev-parse','--absolute-git-dir') for p in projects})==3,
   shared_files=os.path.samefile(first/'src/product.py',second/'src/product.py'),
   other_products_unchanged=(second/'src/product.py').read_bytes()==(third/'src/product.py').read_bytes(),
   branch_leaked=bool(git(second,'branch','--list','private-one')),
   alternates=any((p/'.git/objects/info/alternates').exists() for p in projects),
   object_max_links=max((f.stat().st_nlink for p in projects for f in (p/'.git/objects').rglob('*') if f.is_file()),default=1),
   configs=[{key:git(p,'config','--local','--get',key) for key in ('core.autocrlf','maintenance.autoDetach','gc.autoDetach')} for p in projects],
   positive_exit=positive.returncode,positive_output=positive.stdout+positive.stderr,
   negative_exit=negative.returncode,negative_output=negative.stdout+negative.stderr,
   clean_other_products=all(not git(p,'status','--porcelain') for p in (second,third)))
except Exception as error:
 report.update(error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
finally:
 kind.doClassCleanups()
report.update(full_stages=sum('add' in a and a[a.index('add')+1:]==['.'] for a in events),
 bootstrap_calls=sum(any(v.endswith('bootstrap_project.py') for v in a) and '--apply' in a for a in events),
 clones=sum('clone' in a for a in events),cleanup_errors=len(getattr(kind,'tearDown_exceptions',[])),
 changed_during_preparation=changed_during_preparation,cache_published=getattr(kind,'_product_cache',None) is not None)
print(json.dumps(report))
'''


class FixtureSnapshot(unittest.TestCase):
    def probe(self,mode):
        area=tempfile.TemporaryDirectory(prefix='kdd snapshot probe ');self.addCleanup(area.cleanup)
        source=Path(area.name)/'source';(source/'scripts').mkdir(parents=True)
        for path in (ROOT/'scripts').glob('*.py'):shutil.copyfile(path,source/'scripts'/path.name)
        workflow=source/'.github/workflows/validate.yml';workflow.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/'.github/workflows/validate.yml',workflow)
        (source/'README.md').write_text('# Controlled initialized product\n',encoding='utf-8')
        (source/'.gitignore').write_text('__pycache__/\n*.pyc\n',encoding='utf-8')
        for folder in ('src','tests'):
            (source/folder).mkdir();(source/folder/'.fixture-keep').write_text('',encoding='utf-8')
        work=Path(area.name)/'work';work.mkdir()
        p=subprocess.run([sys.executable,'-X','utf8','-c',PROBE,str(ROOT),str(source),str(work),mode],
            cwd=ROOT,env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,encoding='utf-8',timeout=180)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        return json.loads(p.stdout)

    def test_three_fresh_clones_share_preparation_but_not_files_refs_or_objects(self):
        result=self.probe('shared')
        self.assertIsNone(result['error'],result)
        self.assertEqual((result['full_stages'],result['bootstrap_calls'],result['clones']),(1,0,3))
        self.assertTrue(result['same_refs'] and result['same_trees'] and result['own_git_dirs'])
        self.assertFalse(result['shared_files'] or result['branch_leaked'] or result['alternates'])
        self.assertEqual(result['object_max_links'],1)
        self.assertTrue(result['other_products_unchanged'] and result['clean_other_products'])
        for config in result['configs']:self.assertEqual(set(config.values()),{'false'})
        self.assertEqual(result['positive_exit'],0,result['positive_output'])
        self.assertIn('PASS quality: integrity, perimeter and all checks verified twice',result['positive_output'])
        self.assertEqual(result['positive_output'].count('RUN '),6)
        self.assertNotIn('SKIP',result['positive_output'])
        self.assertNotEqual(result['negative_exit'],0)
        self.assertIn('Check failed: functional',result['negative_output'])
        self.assertEqual(result['cleanup_errors'],0)

    def test_changed_bytes_invalidate_snapshot_with_same_name_size_and_mtime(self):
        result=self.probe('changed')
        self.assertIsNone(result['error'],result)
        self.assertEqual((result['full_stages'],result['bootstrap_calls'],result['clones']),(2,0,2))
        self.assertEqual(result['notes'],['one','two'])
        self.assertTrue(result['same_size'] and result['same_mtime'])
        self.assertTrue(result['refs_changed'] and result['trees_changed'])
        self.assertEqual(result['cleanup_errors'],0)

    def test_partial_template_fails_before_bootstrap_or_git_preparation(self):
        result=self.probe('partial')
        self.assertEqual(result['error_type'],'ValueError',result)
        self.assertIn('manifest',result['error'].lower())
        self.assertEqual((result['full_stages'],result['bootstrap_calls'],result['clones']),(0,0,0))
        self.assertEqual(result['cleanup_errors'],0)

    def test_source_change_during_preparation_never_publishes_snapshot(self):
        result=self.probe('during')
        self.assertEqual(result['error_type'],'ValueError',result)
        self.assertIn('sources changed',result['error'].lower())
        self.assertTrue(result['changed_during_preparation'])
        self.assertFalse(result['cache_published'])
        self.assertEqual(result['clones'],0)
        self.assertEqual(result['cleanup_errors'],0)


class InitializedSnapshot(unittest.TestCase):
    def test_initialized_source_without_git_keeps_new_controls_and_exact_old_applicability(self):
        from scripts.init_project import MANIFEST
        with tempfile.TemporaryDirectory(prefix='kdd snapshot initialized source ') as area:
            project=Path(area)/'project'
            def ignore(directory,names):
                omitted={'.git','node_modules','__pycache__','.audit'}
                if Path(directory).name=='.agents':omitted.add('logs')
                return [name for name in names if name in omitted or name.endswith('.gate.md')]
            shutil.copytree(ROOT,project,ignore=ignore)
            if all((project/name).exists() for name in MANIFEST):
                p=subprocess.run([sys.executable,'-X','utf8','scripts/init_project.py','--apply','--repository','ExampleCo/FixtureSnapshot'],
                    cwd=project,capture_output=True,text=True,encoding='utf-8',timeout=60)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            helper=project/'tests/test_init_project.py'
            if helper.exists():helper.unlink()
            self.assertFalse((project/'.git').exists())
            self.assertFalse(any((project/name).exists() for name in MANIFEST))
            old=['tests.test_approval_routing.TestApprovalRouting.'+name for name in (
                'test_initialized_project_uses_selected_refs_and_runs_real_quality_twice',
                'test_initialized_project_rejects_missing_quality_before_product_checks',
                'test_initialized_copy_marks_only_template_bootstrap_cases_inapplicable')]
            code=('import io,json,unittest\nloader=unittest.TestLoader()\n'
                'suite=loader.loadTestsFromNames('+repr(['tests.test_ci_product_fixture_snapshot.FixtureSnapshot',*old])+')\n'
                'r=unittest.TextTestRunner(stream=io.StringIO()).run(suite)\n'
                'print(json.dumps(dict(tests=r.testsRun,errors=[(c.id(),d) for c,d in r.errors],failures=[(c.id(),d) for c,d in r.failures],'
                'skipped=[(c.id(),why) for c,why in r.skipped],loader_errors=loader.errors)))\n')
            p=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=project,env=dict(os.environ,PYTHONUTF8='1'),
                capture_output=True,text=True,encoding='utf-8',timeout=240)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            result=json.loads(p.stdout)
            self.assertEqual(result['tests'],7)
            self.assertEqual(result['errors'],[])
            self.assertEqual(result['failures'],[],result)
            self.assertEqual(result['loader_errors'],[])
            self.assertEqual({name for name,_ in result['skipped']},set(old))
            self.assertEqual({why for _,why in result['skipped']},{'template-only bootstrap integration: project already initialized'})


if __name__=='__main__':unittest.main()
