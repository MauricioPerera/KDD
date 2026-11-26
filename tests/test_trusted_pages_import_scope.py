"""Verify the Pages change boundary against real Git trees and the guard CLI."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import guard_pr_baseline as guard  # noqa: E402

PAGE = 'site/index.html'


class TrustedPagesImportScope(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-page-guard-')
        self.addCleanup(area.cleanup)
        self.root = Path(area.name).resolve()
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        self.git('init', '-q', '-b', 'main', '--template=')
        configure_git(self.root, {
            'user.name': 'Pages fixture',
            'user.email': 'fixture@example.invalid',
            'core.autocrlf': 'false',
            'commit.gpgsign': 'false',
        }, ephemeral=True)
        self.write('knowledge/contracts/proof.md',
                   "---\ntype: 'Task Contract'\ntests: 'tests/proof.py'\n---\n")
        self.write('tests/proof.py', 'assert len("proof") == 5\n')
        self.write(PAGE, '<h1>Published landing page</h1>\n')
        self.write('site/other.html', '<h1>Other page</h1>\n')
        self.write('scripts/site/index.html', '<h1>Other directory</h1>\n')
        self.base = self.commit('Published baseline')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root,
                                       stderr=subprocess.PIPE, timeout=30).decode('utf-8').strip()

    def write(self, file, text):
        path = self.root / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')

    def commit_index(self, message):
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def commit(self, message):
        self.git('add', '-A')
        return self.commit_index(message)

    def assert_shadows(self, changes, candidate, base=None):
        expected = sorted(path + ': trusted import name changed in PR' for path in changes)
        self.assertEqual(guard.check(base or self.base, candidate, self.base), expected)

    def test_cli_accepts_regular_page_edit_in_real_proposed_merge(self):
        self.git('checkout', '-qb', 'candidate')
        self.write(PAGE, '<h1>Knowledge-Driven Development</h1>\n')
        head = self.commit('Edit the existing page')
        self.git('checkout', '-q', 'main')
        self.write('.github/workflows/validate.yml', 'name: Trusted base check\n')
        base = self.commit('Advance trusted base')
        self.git('merge', '--no-ff', '-qm', 'Proposed merge', head)
        merge = self.git('rev-parse', 'HEAD')
        tree = self.git('rev-parse', merge + '^{tree}')
        self.assertNotEqual(tree, self.git('rev-parse', head + '^{tree}'))
        self.git('update-ref', 'refs/pull/225/merge', merge)
        self.git('remote', 'add', 'origin', str(self.root))
        self.git('checkout', '--quiet', '--detach', base)
        (self.root / PAGE).unlink()
        previous_status = self.git('status', '--porcelain')
        self.assertIn(PAGE, previous_status)
        registry = json.dumps({'schema_version': 1, 'trees': {tree: {'baseline_ref': self.base}}})
        env = dict(os.environ, PYTHONUTF8='1')
        env.pop('KDD_TRUSTED_CHANGE_REVIEW', None)
        result = subprocess.run(
            [sys.executable, '-B', str(ROOT / 'scripts/guard_pr_baseline.py'),
             '--pr-number', '225', '--base-ref', base, '--head-ref', head,
             '--approval-registry', registry],
            cwd=self.root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS: trusted PR baseline and gate files', result.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), base)
        self.assertEqual(self.git('status', '--porcelain'), previous_status)

    def test_regular_page_edit_does_not_hide_a_protected_change(self):
        self.write(PAGE, '<h1>Edited landing page</h1>\n')
        path = 'scripts/guard_pr_baseline.py'
        self.write(path, '# A proposed change to the gate\n')
        candidate = self.commit('Edit the page and a protected file')
        self.assertEqual(guard.check(self.base, candidate, self.base),
                         [path + ': trusted gate file changed in PR'])

    def test_regular_page_edit_does_not_hide_oracle_drift(self):
        self.write(PAGE, '<h1>Edited landing page</h1>\n')
        self.write('tests/proof.py', 'assert len("changed proof") == 13\n')
        candidate = self.commit('Edit the page and the oracle')
        self.assertEqual(guard.check(self.base, candidate, self.base),
                         ['tests/proof.py: oracle differs from approved baseline'])

    def test_regular_page_edit_does_not_hide_contract_drift(self):
        self.write(PAGE, '<h1>Edited landing page</h1>\n')
        path = 'knowledge/contracts/proof.md'
        existing = (self.root / path).read_text(encoding='utf-8')
        self.write(path, existing + '\nUpdated guarantee.\n')
        candidate = self.commit('Edit the page and the contract')
        self.assertEqual(guard.check(self.base, candidate, self.base),
                         [path + ': contract differs from approved baseline'])

    def test_other_site_and_import_paths_keep_their_findings(self):
        self.write(PAGE, '<h1>Edited landing page</h1>\n')
        paths = ('site.py', 'site/__init__.py', 'site/other.html', 'scripts/site/index.html')
        for path in paths:
            self.write(path, '')
        self.assert_shadows(paths, self.commit('Add adjacent paths'))

    def test_creating_the_page_remains_blocked(self):
        self.git('rm', PAGE)
        without_page = self.commit_index('Base without an existing landing page')
        self.write(PAGE, '<h1>New landing page</h1>\n')
        self.assert_shadows([PAGE], self.commit('Add the page'), base=without_page)

    def test_removing_or_moving_the_page_remains_blocked(self):
        self.git('mv', PAGE, 'landing.html')
        candidate = self.commit_index('Rename the page outside the reserved path')
        self.assert_shadows([PAGE], candidate)

    def test_modes_other_than_regular_non_executable_remain_blocked(self):
        blob = self.git('rev-parse', self.base + ':' + PAGE)
        for mode, object_id in (('100755', blob), ('120000', blob), ('160000', self.base)):
            with self.subTest(mode=mode):
                self.git('update-index', '--cacheinfo', f'{mode},{object_id},{PAGE}')
                candidate = self.commit_index('Replace the landing page entry')
                self.assert_shadows([PAGE], candidate)

    def test_directory_replacement_stays_rejected_without_an_error(self):
        self.git('rm', PAGE)
        nested = PAGE + '/other.txt'
        self.write(nested, 'Ordinary file below the old page name\n')
        self.assert_shadows([PAGE, nested], self.commit('Replace the page with a directory'))

    def test_git_replacement_does_not_change_the_original_page_mode(self):
        self.write(PAGE, '<h1>Regular edited page</h1>\n')
        regular = self.commit('Edit regular landing page')
        blob = self.git('rev-parse', regular + ':' + PAGE)
        self.git('update-index', '--cacheinfo', f'120000,{blob},{PAGE}')
        non_regular = self.commit_index('Change the mode in the proposed tree')
        with patch.dict(os.environ):
            os.environ.pop('GIT_NO_REPLACE_OBJECTS', None)
            self.git('replace', non_regular, regular)
            shown = self.git('ls-tree', non_regular, '--', PAGE)
            original = self.git('--no-replace-objects', 'ls-tree', non_regular, '--', PAGE)
            self.assertTrue(shown.startswith('100644 blob '), shown)
            self.assertTrue(original.startswith('120000 blob '), original)
            self.assert_shadows([PAGE], non_regular)

    def test_restoring_a_regular_page_from_an_executable_base_remains_blocked(self):
        blob = self.git('rev-parse', self.base + ':' + PAGE)
        self.git('update-index', '--cacheinfo', f'100755,{blob},{PAGE}')
        executable_base = self.commit_index('Base with different mode')
        self.git('update-index', '--cacheinfo', f'100644,{blob},{PAGE}')
        self.assert_shadows([PAGE], self.commit_index('Restore the regular mode'), base=executable_base)


if __name__ == '__main__':
    unittest.main()
