"""Real Git preparation, private copies and strict failure cleanup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import hashlib,json,os,shutil,subprocess,sys,tempfile,traceback
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from tests import test_validate_change_contract as source
kind=source.ChangeContractTests
method='test_target_change_with_stdlib_import_passes'
trace_area=tempfile.TemporaryDirectory(prefix='kdd-seed-trace-')
trace=Path(trace_area.name)/'git.jsonl';os.environ['GIT_TRACE2_EVENT']=str(trace)
directories=[];cases=[];report={'error':None}
def observe(event,args):
 if event=='tempfile.mkdtemp':directories.append(Path(args[0]))
sys.addaudithook(observe)
def roots():
 events=[json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()] if trace.exists() else []
 commands=[e['argv'] for e in events if e.get('event')=='start']
 return [Path(a[2]) for a in commands if len(a)>3 and Path(a[0]).stem.lower()=='git' and a[1]=='-C' and a[3]=='init']
def git(root,*args):
 return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE).decode('utf-8').strip()
def files(root):
 return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
         for p in root.rglob('*') if p.is_file()}
def fresh():
 case=kind(method);cases.append(case);case.setUp();return case
def cleanup():
 for case in reversed(cases):case.doCleanups()
 cases.clear();kind.doClassCleanups()
try:
 mode=sys.argv[2]
 if mode=='copies':
  kind.setUpClass();seed_roots=roots()[:]
  one,two,three=fresh(),fresh(),fresh()
  prepared=roots()[:]
  before_two,before_three=files(two.root),files(three.root)
  seed=seed_roots[0] if seed_roots else None
  before_seed=files(seed) if seed else None
  oid=git(one.root,'rev-parse','HEAD:src/app.py')
  obj=Path('.git/objects')/oid[:2]/oid[2:]
  shared=os.path.samefile(one.root/'src/app.py',two.root/'src/app.py') or os.path.samefile(one.root/obj,two.root/obj)
  one._write('src/app.py','def value():\n    return 999\n')
  one._write('untracked.txt','private case\n')
  one._git('add','src/app.py');one._git('branch','private-one');one._git('config','user.name','private case')
  (one.root/obj).chmod(0o600)
  (one.root/obj).unlink()
  unchanged=files(two.root)==before_two and files(three.root)==before_three
  seed_unchanged=files(seed)==before_seed if seed else True
  report.update(preparations=len(prepared),shared_files=shared,other_copies_unchanged=unchanged,
   seed_unchanged=seed_unchanged,distinct_roots=len({str(c.root) for c in (one,two,three)})==3,
   shared_baseline=one.base==two.base==three.base,
   other_heads_valid=all(git(c.root,'rev-parse','HEAD')==c.base for c in (two,three)),
   other_checkouts_clean=all(not git(c.root,'status','--porcelain') for c in (two,three)),
   other_objects_valid=all(git(c.root,'cat-file','-t',oid)=='blob' for c in (two,three)),
   branch_leaked=bool(git(two.root,'branch','--list','private-one')),
   own_git_dirs=len({git(c.root,'rev-parse','--absolute-git-dir') for c in (one,two,three)})==3,
   alternates=any((c.root/'.git/objects/info/alternates').exists() for c in (one,two,three)),
   max_links=max(p.stat().st_nlink for c in (two,three) for p in (c.root/'.git/objects').rglob('*') if p.is_file()))
  cleanup();report['all_temporaries_cleaned']=all(not p.exists() for p in directories)
 elif mode=='copy_failure':
  kind.setUpClass();seed_roots=roots()[:];report['seed_available']=len(seed_roots)==1
  if seed_roots:
   old_factory=tempfile.TemporaryDirectory;failed=[]
   def conflict(*args,**kwargs):
    area=old_factory(*args,**kwargs);failed.append(Path(area.name))
    (Path(area.name)/'.git').write_text('real destination collision',encoding='utf-8')
    return area
   case=kind(method);cases.append(case)
   with patch.object(source.tempfile,'TemporaryDirectory',side_effect=conflict):
    try:case.setUp();report['copy_failed']=False
    except (OSError,shutil.Error):report['copy_failed']=True
   case.doCleanups();cases.remove(case)
   report['failed_copy_cleaned']=all(not p.exists() for p in failed)
   recovered=fresh();report['recovery_valid']=git(recovered.root,'rev-parse','HEAD')==recovered.base
   cleanup();report['first_class_cleaned']=not seed_roots[0].exists()
   kind.setUpClass();second_roots=roots()[:];again=fresh()
   report.update(preparations=len(second_roots),different_seed=second_roots[0]!=second_roots[1],
                 second_class_valid=git(again.root,'rev-parse','HEAD')==again.base)
   cleanup();report['all_temporaries_cleaned']=all(not p.exists() for p in directories)
 else:
  original=os.environ.get('GIT_CONFIG_COUNT');os.environ['GIT_CONFIG_COUNT']='-1'
  try:
   try:kind.setUpClass();report['preparation_failed']=False
   except subprocess.CalledProcessError:report['preparation_failed']=True
  finally:
   if original is None:os.environ.pop('GIT_CONFIG_COUNT',None)
   else:os.environ['GIT_CONFIG_COUNT']=original
   kind.doClassCleanups()
  report['failed_preparation_cleaned']=all(not p.exists() for p in directories)
  kind.setUpClass();case=fresh()
  report['recovery_valid']=git(case.root,'rev-parse','HEAD')==case.base
  cleanup();report['all_temporaries_cleaned']=all(not p.exists() for p in directories)
except Exception as error:
 report.update(error=str(error),error_type=type(error).__name__,traceback=traceback.format_exc())
finally:
 cleanup()
report['class_cleanup_errors']=len(getattr(kind,'tearDown_exceptions',[]))
trace_area.cleanup()
print(json.dumps(report))
'''


class ChangeFixtureSeed(unittest.TestCase):
    def probe(self, mode):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', PROBE, str(ROOT), mode],
            cwd=ROOT, env=dict(os.environ, PYTHONUTF8='1', GIT_CONFIG_GLOBAL=os.devnull,
                              GIT_CONFIG_NOSYSTEM='1'),
            capture_output=True, text=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIsNone(report['error'], report)
        self.assertEqual(report['class_cleanup_errors'], 0, report)
        return report

    def test_one_preparation_has_private_files_index_objects_config_and_refs(self):
        report = self.probe('copies')
        self.assertEqual(report['preparations'], 1, report)
        for key in ('other_copies_unchanged', 'seed_unchanged', 'distinct_roots',
                    'shared_baseline', 'other_heads_valid', 'other_checkouts_clean',
                    'other_objects_valid', 'own_git_dirs', 'all_temporaries_cleaned'):
            self.assertTrue(report[key], (key, report))
        self.assertFalse(report['shared_files'] or report['branch_leaked'] or report['alternates'], report)
        self.assertEqual(report['max_links'], 1, report)

    def test_copy_collision_cleans_and_new_class_invocation_prepares_again(self):
        report = self.probe('copy_failure')
        self.assertTrue(report['seed_available'], report)
        for key in ('copy_failed', 'failed_copy_cleaned', 'recovery_valid',
                    'first_class_cleaned', 'different_seed', 'second_class_valid',
                    'all_temporaries_cleaned'):
            self.assertTrue(report[key], (key, report))
        self.assertEqual(report['preparations'], 2, report)

    def test_git_preparation_failure_cleans_and_is_not_cached(self):
        report = self.probe('preparation_failure')
        self.assertTrue(report['preparation_failed'], report)
        for key in ('failed_preparation_cleaned', 'recovery_valid', 'all_temporaries_cleaned'):
            self.assertTrue(report[key], (key, report))


if __name__ == '__main__':
    unittest.main()
