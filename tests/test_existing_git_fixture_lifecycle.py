"""Local policy and real Trace2 for the two fixtures that failed in CI."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import test_task_git as tasks
import test_validate_change_contract as changes


class ExistingGitFixtureLifecycle(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-existing-git-lifecycle-')
        self.addCleanup(self.area.cleanup)
        self.trace = Path(self.area.name) / 'trace.jsonl'
        settings = patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': os.devnull,
                                          'GIT_CONFIG_NOSYSTEM': '1',
                                          'GIT_TRACE2_EVENT': str(self.trace)})
        settings.start()
        self.addCleanup(settings.stop)

    def fixture(self, kind):
        if kind == 'tasks':
            instance = tasks.Repository()
            self.addCleanup(instance.close)
            return instance.root, instance.commit
        instance = changes.ChangeContractTests('test_target_change_with_stdlib_import_passes')
        self.addCleanup(instance.doCleanups)
        instance.setUp()
        return instance.root, instance._commit

    def git(self, root, *arguments):
        return subprocess.run(['git', '-C', str(root), *arguments],
                              capture_output=True, text=True, encoding='utf-8', timeout=30)

    def local_policy(self, kind):
        root, _ = self.fixture(kind)
        for key in ('maintenance.autoDetach', 'gc.autoDetach'):
            value = self.git(root, 'config', '--local', '--get', key)
            self.assertEqual(value.returncode, 0, key + ' missing from the fixture')
            self.assertEqual(value.stdout.strip(), 'false')
            origin = self.git(root, 'config', '--show-origin', '--get', key)
            self.assertEqual(origin.returncode, 0)
            self.assertTrue(origin.stdout.startswith('file:.git/config'), origin.stdout)

    def maintenance_enabled(self, kind):
        root, _ = self.fixture(kind)
        for key, disabled in [('maintenance.auto', 'false'), ('gc.auto', '0')]:
            value = self.git(root, 'config', '--get', key)
            self.assertIn(value.returncode, (0, 1))
            self.assertNotEqual(value.stdout.strip(), disabled)

    def synchronous_commit(self, kind):
        root, commit = self.fixture(kind)
        (root / 'extra.txt').write_text('another real commit\n', encoding='utf-8')
        commit('Lifecycle proof')
        events = [json.loads(line) for line in self.trace.read_text(encoding='utf-8').splitlines()]
        names = {e['sid']: e.get('name') for e in events if e['event'] == 'cmd_name'}
        commits = [sid for sid, name in names.items() if name == 'commit']
        self.assertEqual(len(commits), 2, 'Initial and later commit must both be covered')
        version = tuple(map(int, re.search(r'(\d+)\.(\d+)', self.git(root, '--version').stdout).groups()))
        for sid in commits:
            starts = [e for e in events if e['event'] == 'child_start' and e['sid'] == sid
                      and any(a in ('maintenance', 'gc') for a in e.get('argv', []))]
            self.assertTrue(starts, 'Real automatic maintenance must still run')
            for start in starts:
                self.assertNotIn('--detach', start['argv'])
                if version >= (2, 47) and 'maintenance' in start['argv']:
                    self.assertIn('--no-detach', start['argv'])
            parent_end = [i for i, e in enumerate(events) if e['event'] == 'exit' and e['sid'] == sid]
            child_end = [i for i, e in enumerate(events) if e['event'] == 'exit'
                         and e['sid'].startswith(sid + '/') and names.get(e['sid']) in ('maintenance', 'gc')]
            self.assertEqual(len(parent_end), 1)
            self.assertTrue(child_end, 'Maintenance must finish before cleanup can start')
            self.assertLess(max(child_end), parent_end[0])
            self.assertTrue(all(events[i]['code'] == 0 for i in parent_end + child_end))

    def test_tasks_policy_is_local_before_initial_commit(self):
        self.local_policy('tasks')

    def test_changes_policy_is_local_before_initial_commit(self):
        self.local_policy('changes')

    def test_tasks_maintenance_remains_enabled(self):
        self.maintenance_enabled('tasks')

    def test_changes_maintenance_remains_enabled(self):
        self.maintenance_enabled('changes')

    def test_tasks_maintenance_finishes_before_each_commit_returns(self):
        self.synchronous_commit('tasks')

    def test_changes_maintenance_finishes_before_each_commit_returns(self):
        self.synchronous_commit('changes')


if __name__ == '__main__':
    unittest.main()
