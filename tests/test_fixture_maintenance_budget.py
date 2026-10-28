"""Real Trace2 process budgets, immutable Git results and local fixture modes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.test_fixture_preparation import configure_git
from tests.test_generated_task_evidence import TaskProject
from tests.test_task_git import Repository


class FixtureMaintenanceBudget(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd fixture budget ')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.global_config = self.area / 'owned-user-config'
        self.global_config.write_text('[user]\n\tname = External sentinel\n')
        self.settings = patch.dict(os.environ, {
            'GIT_CONFIG_GLOBAL': str(self.global_config), 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_DATE': '2001-01-01T00:00:00+0000',
            'GIT_COMMITTER_DATE': '2001-01-01T00:00:00+0000'})
        self.settings.start(); self.addCleanup(self.settings.stop)
        self.trace = self.area / 'trace.jsonl'
        self.values = {'user.name': 'Own fixture', 'user.email': 'fixture@example.invalid',
            'maintenance.autoDetach': 'false', 'gc.autoDetach': 'false', 'commit.gpgsign': 'false'}

    def git(self, root, *args, trace=False):
        env = dict(os.environ)
        if trace:
            env['GIT_TRACE2_EVENT'] = str(self.trace)
        result = subprocess.run(['git', '-C', str(root), *args], env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def fresh(self, name, **kwargs):
        root = self.area / name; root.mkdir()
        self.git(root, 'init', '-q', '-b', 'main', '--object-format=sha1')
        configure_git(root, self.values, **kwargs)
        return root

    def events(self):
        return [json.loads(line) for line in self.trace.read_text(encoding='utf-8').splitlines()]

    def housekeeping(self, events):
        return [event for event in events if event['event'] == 'child_start'
                and any(arg in ('maintenance', 'gc') for arg in event.get('argv', []))]

    def test_ephemeral_local_settings_exist_before_the_first_commit(self):
        root = self.fresh('ephemeral', ephemeral=True)
        for key, expected in (('maintenance.auto', 'false'), ('gc.auto', '0'),
                              ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')):
            self.assertEqual(self.git(root, 'config', '--local', '--get', key), expected)
            self.assertTrue(self.git(root, 'config', '--show-origin', '--get', key).startswith('file:.git/config'))
        self.assertFalse((root / '.git/refs/heads/main').exists())
        self.assertFalse((root / '.git/index').exists())

    def test_six_ephemeral_commits_have_no_housekeeping_children(self):
        root = self.fresh('ephemeral', ephemeral=True)
        for number in range(6):
            self.git(root, 'commit', '--allow-empty', '-qm', 'Commit ' + str(number), trace=True)
        events = self.events()
        self.assertEqual(len([e for e in events if e['event'] == 'start']), 6)
        self.assertEqual(self.housekeeping(events), [])
        self.assertEqual(self.git(root, 'rev-list', '--count', 'HEAD'), '6')
        self.assertEqual(self.git(root, 'status', '--porcelain'), '')

    def test_default_mode_still_runs_real_synchronous_maintenance(self):
        root = self.fresh('dedicated')
        self.git(root, 'commit', '--allow-empty', '-qm', 'Synchronous proof', trace=True)
        events = self.events(); children = self.housekeeping(events)
        self.assertTrue(children)
        names = {e['sid']: e.get('name') for e in events if e['event'] == 'cmd_name'}
        parent = next(sid for sid, name in names.items() if name == 'commit')
        parent_end = next(i for i, e in enumerate(events) if e['event'] == 'exit' and e['sid'] == parent)
        ends = [i for i, e in enumerate(events) if e['event'] == 'exit'
                and e['sid'].startswith(parent + '/') and names.get(e['sid']) in ('maintenance', 'gc')]
        self.assertTrue(ends); self.assertLess(max(ends), parent_end)
        self.assertTrue(all(events[i]['code'] == 0 for i in ends))
        self.assertTrue(all('--detach' not in e['argv'] for e in children))

    def test_mode_does_not_change_real_commits_or_trees(self):
        results = []
        for mode in (False, True):
            root = self.fresh(str(mode), ephemeral=mode)
            (root / 'product.txt').write_bytes(b'identical product\n')
            self.git(root, 'add', 'product.txt')
            for number in range(3):
                self.git(root, 'commit', '--allow-empty', '-qm', 'Same product ' + str(number))
            results.append((self.git(root, 'rev-parse', 'HEAD'), self.git(root, 'rev-parse', 'HEAD^{tree}'),
                            self.git(root, 'log', '--format=%H %P')))
        self.assertEqual(results[0], results[1])

    def test_configuration_never_changes_owned_external_config(self):
        before = self.global_config.read_bytes()
        root = self.fresh('local only', ephemeral=True)
        self.git(root, 'commit', '--allow-empty', '-qm', 'Own commit')
        self.assertEqual(self.global_config.read_bytes(), before)
        self.assertEqual(self.git(root, 'config', '--global', '--get', 'user.name'), 'External sentinel')

    def test_non_boolean_modes_reject_before_config_write(self):
        root = self.fresh('invalid'); original = (root / '.git/config').read_bytes()
        for value in (0, 1, None, 'false', [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                configure_git(root, self.values, ephemeral=value)
            self.assertEqual((root / '.git/config').read_bytes(), original)

    def test_hardlinked_config_rejects_ephemeral_mode_without_touching_canary(self):
        root = self.fresh('shared'); config = root / '.git/config'
        canary = self.area / 'external-config'; os.link(config, canary)
        before = canary.read_bytes()
        with self.assertRaises(ValueError):
            configure_git(root, self.values, ephemeral=True)
        self.assertEqual(canary.read_bytes(), before)
        self.assertEqual(config.read_bytes(), before)

    def test_repository_default_does_not_start_housekeeping(self):
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(self.trace)}):
            repo = Repository(); self.addCleanup(repo.close)
            repo.act('create')
        self.assertEqual(self.housekeeping(self.events()), [])
        self.assertEqual(repo.git('rev-list', '--count', 'HEAD'), '2')

    def test_repository_dedicated_mode_keeps_housekeeping(self):
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(self.trace)}):
            repo = Repository(automatic_maintenance=True); self.addCleanup(repo.close)
        self.assertTrue(self.housekeeping(self.events()))
        self.assertEqual(repo.git('rev-list', '--count', 'HEAD'), '1')

    def test_task_project_default_does_not_start_housekeeping(self):
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(self.trace)}):
            project = TaskProject(self.area / 'project')
        self.assertEqual(self.housekeeping(self.events()), [])
        self.assertEqual(project.git('rev-list', '--count', 'HEAD'), '1')

    def test_task_project_dedicated_mode_keeps_housekeeping(self):
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(self.trace)}):
            project = TaskProject(self.area / 'project', automatic_maintenance=True)
        self.assertTrue(self.housekeeping(self.events()))
        self.assertEqual(project.git('rev-list', '--count', 'HEAD'), '1')

    def test_empty_configuration_cannot_modify_the_fixture(self):
        root = self.fresh('empty'); before = (root / '.git/config').read_bytes()
        with self.assertRaises(ValueError):
            configure_git(root, {}, ephemeral=True)
        self.assertEqual((root / '.git/config').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
