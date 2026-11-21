"""Check the bounded profile fixture without replacing any of its real runs."""

import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.init_project import MANIFEST
from tests import test_ci_windows_suite_profile as profile
from tests.test_fixture_preparation import directory_alias


REQUIRED = (
    '.github/workflows/validate.yml',
    'tests/__init__.py',
    'tests/test_ci_windows_suite_profile.py',
    'tests/test_fixture_preparation.py',
    'scripts/init_project.py',
    'scripts/bootstrap_transaction.py',
    *('scripts/' + name for name in profile.RUNTIME),
)
OPTIONAL = 'tests/test_init_project.py'


class InitializedProfileCopy(unittest.TestCase):
    def setUp(self):
        self.area = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source = self.area / 'source'
        self.source.mkdir()

    def copy(self, name):
        destination = self.area / name
        with patch.object(profile, 'ROOT', self.source):
            profile.copy_profile_source(destination)
        return destination

    def write(self, name, value):
        target = self.source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)

    def test_initialized_copy_preserves_exact_bytes_and_isolation(self):
        for name in REQUIRED:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(profile.ROOT / name, target)
        self.write(OPTIONAL, b'bootstrap helper canary')
        self.write('docs/canary.txt', b'not used by the profile')
        first, second = self.copy('first'), self.copy('second')
        expected = {name: (self.source / name).read_bytes() for name in (*REQUIRED, OPTIONAL)}
        for project in (first, second):
            actual = {path.relative_to(project).as_posix(): path.read_bytes()
                      for path in project.rglob('*') if path.is_file()}
            self.assertEqual(set(actual), set(expected))
            self.assertEqual(actual, expected)
        (first / OPTIONAL).unlink()
        (first / REQUIRED[0]).write_bytes(b'changed')
        self.assertTrue((second / OPTIONAL).is_file())
        self.assertEqual((second / REQUIRED[0]).read_bytes(), expected[REQUIRED[0]])
        self.assertEqual((self.source / REQUIRED[0]).read_bytes(), expected[REQUIRED[0]])
        (self.source / OPTIONAL).unlink()
        self.assertFalse((self.copy('without-helper') / OPTIONAL).exists())

    def test_partial_template_retains_full_copy_with_previous_exclusions(self):
        self.write(MANIFEST[0], b'example still present')
        self.write('docs/canary.txt', b'ordinary file')
        self.write('.git/probe', b'excluded')
        self.write('node_modules/probe', b'excluded')
        self.write('.agents/logs/probe', b'excluded')
        project = self.copy('partial')
        self.assertEqual((project / MANIFEST[0]).read_bytes(), b'example still present')
        self.assertEqual((project / 'docs/canary.txt').read_bytes(), b'ordinary file')
        for name in ('.git', 'node_modules', '.agents/logs'):
            with self.subTest(path=name):
                self.assertFalse((project / name).exists())

    def test_dangling_manifest_entry_uses_the_full_copy_and_fails(self):
        target = self.area / 'existing-target'
        target.mkdir()
        link = self.source / MANIFEST[0]
        link.parent.mkdir(parents=True, exist_ok=True)
        directory_alias(link, target, self.area)
        self.addCleanup(link.rmdir if os.name == 'nt' else link.unlink)
        target.rmdir()
        self.assertTrue(os.path.lexists(link))
        self.assertFalse(link.exists())
        with self.assertRaises(shutil.Error):
            self.copy('broken-template')

    def test_missing_required_file_in_initialized_source_fails_explicitly(self):
        for name in REQUIRED[1:]:
            self.write(name, b'required source')
        with self.assertRaises(FileNotFoundError) as failure:
            self.copy('missing')
        self.assertEqual(Path(failure.exception.filename), self.source / REQUIRED[0])
