"""Real Git lifecycle: local policy and Trace2 prove synchronous maintenance."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_generated_task_evidence import TaskProject


class GitFixtureLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-git-lifecycle-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_configuration_is_local_and_does_not_disable_maintenance(self):
        project = TaskProject(self.root / 'project', automatic_maintenance=True)
        for key in ('maintenance.autoDetach', 'gc.autoDetach'):
            proc = project.command(['git', 'config', '--local', '--get', key], check=False)
            self.assertEqual(proc.returncode, 0, key + ' must be configured before commits')
            self.assertEqual(proc.stdout.strip(), 'false')
            origin = project.git('config', '--show-origin', '--get', key)
            self.assertTrue(origin.startswith('file:.git/config'), origin)
        for key, disabled in [('maintenance.auto', 'false'), ('gc.auto', '0')]:
            proc = project.command(['git', 'config', '--get', key], check=False)
            self.assertIn(proc.returncode, (0, 1))
            self.assertNotEqual(proc.stdout.strip(), disabled, key + ' must remain enabled')

    def test_real_maintenance_completes_before_commit_exit(self):
        trace = self.root / 'trace.jsonl'
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
            project = TaskProject(self.root / 'project', automatic_maintenance=True)
        project.write('extra.txt', 'one more real commit\n')
        project.commit('Fixture lifecycle proof')
        events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
        names = {event['sid']: event.get('name') for event in events if event['event'] == 'cmd_name'}
        commits = [sid for sid, name in names.items() if name == 'commit']
        self.assertEqual(len(commits), 2)
        version = tuple(map(int, re.search(r'(\d+)\.(\d+)', project.git('--version')).groups()))
        for sid in commits:
            starts = [event for event in events if event['event'] == 'child_start'
                      and event['sid'] == sid
                      and any(part in ('maintenance', 'gc') for part in event.get('argv', []))]
            self.assertTrue(starts, 'real Git must run automatic housekeeping')
            for event in starts:
                self.assertNotIn('--detach', event['argv'])
                if version >= (2, 47) and 'maintenance' in event['argv']:
                    self.assertIn('--no-detach', event['argv'])
            parent_end = [i for i, event in enumerate(events) if event['event'] == 'exit' and event['sid'] == sid]
            children_end = [i for i, event in enumerate(events) if event['event'] == 'exit'
                            and event['sid'].startswith(sid + '/')
                            and names.get(event['sid']) in ('maintenance', 'gc')]
            self.assertEqual(len(parent_end), 1)
            self.assertTrue(children_end, 'housekeeping must finish before fixture cleanup')
            self.assertLess(max(children_end), parent_end[0])
            self.assertTrue(all(events[i]['code'] == 0 for i in children_end + parent_end))


if __name__ == '__main__':
    unittest.main()
