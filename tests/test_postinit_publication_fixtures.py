"""Real Git preparation and private repository state for publication fixtures."""
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests import test_task_git, test_task_import_ancestry, test_task_publication


class PublicationFixtureHeadroom(unittest.TestCase):
    def setUp(self):
        self.area = Path(self.enterContext(tempfile.TemporaryDirectory(
            prefix='kdd-publication-trace-'))).resolve()
        self.traces = 0

    @contextmanager
    def trace(self):
        self.traces += 1
        path = self.area / ('commands-' + str(self.traces) + '.jsonl')
        commands = []
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(path)}):
            yield commands
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                event = json.loads(line)
                if event.get('event') == 'start':
                    commands.append(event['argv'])

    @contextmanager
    def cases(self, Fixture, count=2):
        with ExitStack() as cleanup:
            cleanup.callback(Fixture.doClassCleanups)
            with self.trace() as setup:
                Fixture.setUpClass()
            cases, case_commands = [], []
            for _ in range(count):
                case = Fixture('runTest')
                cleanup.callback(case.doCleanups)
                with self.trace() as commands:
                    case.setUp()
                cases.append(case)
                case_commands.extend(commands)
            yield setup, case_commands, cases

    def test_publication_starts_real_task_once_and_copies_it(self):
        with self.cases(test_task_publication.TaskPublicationTests) as (setup, commands, cases):
            self.assertEqual(sum('init' in argv for argv in setup), 1, setup)
            self.assertEqual(commands, [], commands)
            for case in cases:
                repo = case.repo
                task = (repo.root / case.path).read_text(encoding='utf-8')
                self.assertIn("status: 'in_progress'", task)
                self.assertEqual(repo.git('rev-parse', 'HEAD'), case.start_commit)
                self.assertEqual(repo.git('branch', '--show-current'), 'main')
                self.assertTrue(repo.git('rev-parse', 'refs/heads/task/TASK-001'))
                self.assertFalse((repo.root / 'docs/task-evidence').exists())

    def test_import_builds_real_fork_once_and_copies_it(self):
        with self.cases(test_task_import_ancestry.TaskImportAncestryTests) as (setup, commands, cases):
            self.assertEqual(sum('init' in argv for argv in setup), 1, setup)
            self.assertEqual(commands, [], commands)
            for case in cases:
                repo = case.repo
                self.assertEqual(repo.git('branch', '--show-current'), 'feature')
                self.assertEqual(repo.git('rev-parse', 'main'), case.main_base)
                self.assertEqual(repo.git('merge-base', 'main', 'feature'), repo.approved)
                self.assertEqual(repo.git('show', 'main:knowledge/tasks/TASK-001.md').strip(),
                                 case.task.strip())
                self.assertFalse(case.path.exists())

    def test_product_index_refs_and_objects_are_private(self):
        for fixture in (test_task_publication.TaskPublicationTests, test_task_import_ancestry.TaskImportAncestryTests):
            with self.subTest(fixture=fixture.__name__):
                with self.cases(fixture) as (_, _, (first, second)):
                    a, b = first.repo, second.repo
                    self.assertNotEqual(a.root, b.root)
                    for repo in (a, b):
                        self.assertIsInstance(repo, test_task_git.Repository)
                        self.assertFalse((repo.root / '.git/objects/info/alternates').exists())
                        original_commit = Path('.git/objects', repo.approved[:2], repo.approved[2:])
                        self.assertEqual(repo.git('cat-file', '-t', repo.approved), 'commit')
                        for name in (Path('.git/config'), Path('.git/index'), Path('src/value.py'),
                                     original_commit):
                            self.assertEqual((repo.root / name).stat().st_nlink, 1, name)
                    snapshot = (b.git('show-ref'), (b.root / '.git/index').read_bytes(),
                                (b.root / 'src/value.py').read_bytes(), b.git('config', '--local', '--list'))
                    (a.root / 'src/value.py').write_text('fixture-private\n', encoding='utf-8')
                    new = a.commit('private fixture change')
                    a.git('branch', 'private', new)
                    a.git('config', '--local', 'fixture.private', 'yes')
                    self.assertEqual(snapshot, (b.git('show-ref'), (b.root / '.git/index').read_bytes(),
                                                (b.root / 'src/value.py').read_bytes(),
                                                b.git('config', '--local', '--list')))
                    with self.assertRaises(subprocess.CalledProcessError):
                        b.git('cat-file', '-e', new)

    def test_failed_preparation_can_be_repeated_with_real_git(self):
        class Fixture(test_task_import_ancestry.TaskImportAncestryTests):
            pass

        owner = self.area / 'failed-preparation'
        owner.mkdir()
        try:
            with (patch.object(tempfile, 'tempdir', str(owner)),
                  patch.dict(os.environ, {'GIT_CONFIG_COUNT': 'not-an-integer'})):
                with self.assertRaises(subprocess.CalledProcessError):
                    Fixture.setUpClass()
        finally:
            Fixture.doClassCleanups()
        self.assertEqual(list(owner.iterdir()), [])
        with self.cases(Fixture, count=1) as (setup, commands, (case,)):
            self.assertEqual(sum('init' in argv for argv in setup), 1, setup)
            self.assertEqual(commands, [], commands)
            self.assertEqual(case.repo.git('branch', '--show-current'), 'feature')


    def test_missing_source_fails_and_cleans_the_copy_destination(self):
        seed = test_task_git.Repository()
        self.addCleanup(seed.close)
        copy = getattr(seed, 'independent_copy', None)
        self.assertTrue(callable(copy))
        seed.close()
        owner = self.area / 'failed-copy'
        owner.mkdir()
        with patch.object(tempfile, 'tempdir', str(owner)):
            with self.assertRaises(FileNotFoundError):
                copy()
        self.assertEqual(list(owner.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
