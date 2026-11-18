"""Measure Git setup and check that adoption cases receive private runtime seeds."""
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.adoption_remediation_support import AdoptionIntegration


ROOT = Path(__file__).resolve().parents[1]
PROBE = """
from pathlib import Path
import sys
from tests.adoption_remediation_support import AdoptionIntegration

area = Path(sys.argv[1])
for label in ('one', 'two', 'three'):
    fixture = AdoptionIntegration()
    fixture.root = area / label / 'existing project'
    fixture.root.mkdir(parents=True)
    fixture.seed_repository()
"""


class AdoptionRuntimeFixtureSeed(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-adoption-runtime-fixture-')
        self.addCleanup(area.cleanup)
        self.area = Path(area.name)
        environment = patch.dict(os.environ, {
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_AUTHOR_DATE': '2001-07-22T00:00:00Z',
            'GIT_COMMITTER_DATE': '2001-07-22T00:00:00Z',
        })
        environment.start()
        self.addCleanup(environment.stop)

    def seed(self, label):
        fixture = AdoptionIntegration()
        fixture.root = self.area / label / 'existing project'
        fixture.root.mkdir(parents=True)
        seed, first, second = fixture.seed_repository()
        self.assertTrue(seed.resolve().is_relative_to((self.area / label).resolve()))
        return seed, first, second

    def git(self, root, *args, check=True):
        return subprocess.run(
            ['git', '-C', str(root), *args],
            capture_output=True, encoding='utf-8', timeout=30, check=check,
        )

    def assert_private_seed(self, seed):
        for path in (seed, *seed.rglob('*')):
            mode = path.lstat()
            self.assertFalse(stat.S_ISLNK(mode.st_mode), str(path))
            attributes = getattr(mode, 'st_file_attributes', 0)
            self.assertFalse(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, str(path))
            if not stat.S_ISDIR(mode.st_mode):
                self.assertTrue(stat.S_ISREG(mode.st_mode), str(path))
                self.assertEqual(mode.st_nlink, 1, str(path))

    def assert_initial_seed(self, seed, first, second):
        self.assert_private_seed(seed)
        self.assertNotEqual(first, second)
        self.assertEqual(self.git(seed, 'rev-parse', 'HEAD').stdout.strip(), second)
        self.assertEqual(self.git(seed, 'rev-parse', second + '^').stdout.strip(), first)
        self.assertEqual(self.git(seed, 'rev-list', '--count', second).stdout.strip(), '2')
        self.assertEqual(self.git(seed, 'show', first + ':revision.txt').stdout, 'KDD A')
        self.assertEqual(self.git(seed, 'show', second + ':revision.txt').stdout, 'KDD B')
        self.assertEqual(self.git(seed, 'status', '--porcelain').stdout, '')
        self.assertFalse((seed / '.git/objects/info/alternates').exists())
        helper = 'scripts/validate_test_commands.py'
        self.assertEqual((seed / helper).read_bytes(), (ROOT / helper).read_bytes())

    def test_three_real_seeds_share_the_initial_setup_budget(self):
        trace = self.area / 'runtime setup.jsonl'
        completed = subprocess.run(
            [sys.executable, '-B', '-X', 'utf8', '-c', PROBE, str(self.area)],
            cwd=ROOT, env={**os.environ, 'GIT_TRACE2_EVENT': trace.as_posix()},
            capture_output=True, encoding='utf-8', timeout=90, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        rows = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
        starts = [row for row in rows if row.get('event') == 'start']
        inits = [row['argv'] for row in starts if 'init' in row.get('argv', ())]
        self.assertEqual((len(inits), len(starts) <= 12), (1, True),
                         f'{len(inits)} git init and {len(starts)} Git starts')

    def test_real_revisions_and_tracked_bytes_are_available_per_case(self):
        original = self.seed('one')
        self.assert_initial_seed(*original)
        for label in ('two', 'three'):
            with self.subTest(case=label):
                other = self.seed(label)
                self.assert_initial_seed(*other)
                self.assertEqual(other[1:], original[1:])

    def test_checkout_and_object_changes_stay_in_their_case(self):
        first, _, _ = self.seed('one')
        second, *second_refs = self.seed('two')
        for seed in (first, second):
            self.assert_private_seed(seed)
        (first / 'revision.txt').write_bytes(b'private change\n')
        self.git(first, 'config', 'kdd.fixture-case', 'private')
        self.git(first, 'add', 'revision.txt')
        self.git(first, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Private case change')
        private = self.git(first, 'rev-parse', 'HEAD').stdout.strip()
        for seed, *refs in ((second, *second_refs), self.seed('fresh after change')):
            with self.subTest(case=seed.parent.name):
                self.assert_initial_seed(seed, *refs)
                self.assertNotEqual(self.git(seed, 'cat-file', '-t', private, check=False).returncode, 0)
                self.assertEqual(self.git(seed, 'config', '--local', '--get', 'kdd.fixture-case',
                                          check=False).returncode, 1)


if __name__ == '__main__':
    unittest.main()