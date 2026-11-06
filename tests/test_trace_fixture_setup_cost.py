"""Git process accounting and isolation for traceability integration fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""
import json, os, sys
from pathlib import Path
from tests import test_traceability_model as support
calls=[]
def audit(event, args):
    if event != 'subprocess.Popen': return
    raw=args[1]
    tokens=[str(x).strip('\"') for x in raw] if isinstance(raw,(list,tuple)) else str(raw).split()
    if tokens and os.path.basename(tokens[0].strip('\"')).lower() in ('git','git.exe'):
        calls.append(tokens)
sys.addaudithook(audit)
fixture=support.RepositoryFixture
fixture.setUpClass()
base_config=sum('config' in argv for argv in calls)
case1=fixture(); case2=fixture()
try:
    start=len(calls); case1.setUp(); first=calls[start:]
    source_config=(fixture.base/'.git/config').read_bytes()
    support.git(case1.root,'config','--local','user.name','Changed only in clone')
    support.write(case1.root,'untracked-canary.txt','clone one only')
    start=len(calls); case2.setUp(); second=calls[start:]
    settings={name:support.git(case2.root,'config','--local','--get',name)
              for name in ('user.name','user.email','maintenance.autoDetach','gc.autoDetach')}
    result={
      'base_config_processes':base_config,
      'first_git_processes':len(first),'first_config_processes':sum('config' in a for a in first),
      'second_git_processes':len(second),'second_config_processes':sum('config' in a for a in second),
      'settings':settings,'refs_match':support.git(case2.root,'rev-parse','main')==fixture.refs['closed'],
      'source_config_unchanged':(fixture.base/'.git/config').read_bytes()==source_config,
      'clone_config_independent':support.git(case1.root,'config','--local','--get','user.name')=='Changed only in clone',
      'source_canary_absent':not (fixture.base/'untracked-canary.txt').exists(),
      'second_canary_absent':not (case2.root/'untracked-canary.txt').exists(),
      'trace_exit':support.command(case2.root,[sys.executable,'scripts/traceability.py',
          '--repo-root',str(case2.root),'--ref','main','--manifest','quality/traceability.json',
          '--require-verified']).returncode,
    }
    print(json.dumps(result,sort_keys=True))
finally:
    case2.doCleanups(); case1.doCleanups(); fixture.doClassCleanups()
"""


class TraceFixtureSetupCost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', PROBE], cwd=ROOT,
            env=dict(os.environ, PYTHONUTF8='1'), capture_output=True, text=True,
            encoding='utf-8', timeout=300)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.observed = json.loads(result.stdout)

    def test_initial_setup_does_not_spawn_git_for_each_local_setting(self):
        self.assertEqual(self.observed['base_config_processes'], 0)

    def test_each_clone_uses_only_the_required_real_git_clone(self):
        for prefix in ('first', 'second'):
            with self.subTest(clone=prefix):
                self.assertEqual(self.observed[prefix + '_git_processes'], 1)
                self.assertEqual(self.observed[prefix + '_config_processes'], 0)

    def test_settings_history_and_real_trace_remain_valid(self):
        self.assertEqual(self.observed['settings'], {'user.name': 'Trace case',
            'user.email': 'trace@example.invalid', 'maintenance.autoDetach': 'false', 'gc.autoDetach': 'false'})
        self.assertTrue(self.observed['refs_match'])
        self.assertEqual(self.observed['trace_exit'], 0)

    def test_two_clones_and_source_have_independent_state(self):
        for key in ('source_config_unchanged','clone_config_independent',
                    'source_canary_absent','second_canary_absent'):
            with self.subTest(key=key): self.assertTrue(self.observed[key])


if __name__ == '__main__': unittest.main()
