"""Trace a closed task with actual Git commits and an inventoried oracle."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import test_traceability_model as fixture


CONTRACT = 'knowledge/contracts/value.md'
ORACLE = 'tests/test_value.py'
HELPER = 'tests/helper.py'
BINARY = 'tests/bytes.dat'


def prepare(root):
    write = fixture.write

    def seed(project, path, text):
        if path == CONTRACT:
            (project / HELPER).write_bytes(b'EXPECTED = 7\n')
            (project / ORACLE).write_bytes(oracle.encode('utf-8'))
            (project / BINARY).write_bytes(b'\x00\xffpayload\r\n')
            write(project, '.gitattributes', BINARY + ' -text\n')
            text = text.replace('tests: ' + ORACLE,
                                f'tests: {ORACLE}\ntest_runner: python-unittest\n'
                                f"oracle_files: ['{ORACLE}', '{HELPER}', '{BINARY}']")
        elif path == 'quality/product.json':
            policy = json.loads(text)
            policy['protected'].extend([HELPER, BINARY, '.gitattributes'])
            text = fixture.dump(policy)
        write(project, path, text)

    oracle = fixture.ORACLE.replace('from src.value import value',
                                    'from src.value import value\nfrom tests.helper import EXPECTED')
    oracle = oracle.replace('value(7), 7', 'value(7), EXPECTED')
    with patch.object(fixture, 'write', side_effect=seed), patch.object(fixture, 'ORACLE', oracle):
        return fixture.prepare_project(root)


class InventoryTrace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        area = tempfile.TemporaryDirectory(prefix='kdd-trace-oracles-')
        cls.addClassCleanup(area.cleanup)
        cls.seed = Path(area.name) / 'seed'
        cls.refs = prepare(cls.seed)

    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-trace-case-')
        self.addCleanup(area.cleanup)
        self.repo = Path(area.name) / 'repo'
        fixture.git(Path(area.name), 'clone', '-q', '--shared', str(self.seed), str(self.repo))
        fixture.configure_git(self.repo, {'user.name': 'Trace fixture',
                                          'user.email': 'trace@example.invalid'}, ephemeral=True)

    def git(self, *args):
        return fixture.git(self.repo, *args)

    def trace(self, *args):
        before = (self.git('status', '--porcelain'), self.git('show-ref'))
        result = fixture.command(self.repo, [sys.executable, 'scripts/traceability.py',
                                             '--require-verified', *args])
        self.assertEqual((self.git('status', '--porcelain'), self.git('show-ref')), before)
        return result

    def stale(self):
        result = self.trace()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('TRACE_STALE', result.stdout)
        self.assertEqual(self.trace('--ref', self.refs['closed']).returncode, 0)

    def test_helper_change_breaks_oracle_and_current_trace(self):
        self.assertEqual(self.trace().returncode, 0)
        fixture.write(self.repo, HELPER, 'EXPECTED = 8\n')
        fixture.commit(self.repo, 'Change the inventoried expected value')
        runner = fixture.command(self.repo, [sys.executable, '-m', 'unittest', 'tests.test_value'])
        self.assertIn('AssertionError: 7 != 8', runner.stderr)
        self.stale()

    def test_missing_auxiliary_makes_trace_stale(self):
        self.git('rm', BINARY)
        fixture.commit(self.repo, 'Remove the inventoried fixture')
        self.stale()

    def test_symlink_blob_makes_trace_stale_without_host_symlink_support(self):
        oid = self.git('rev-parse', 'HEAD:' + HELPER)
        self.git('update-index', '--cacheinfo', '120000,' + oid + ',' + HELPER)
        self.git('commit', '-qm', 'Publish nonregular mode')
        self.stale()

    def test_approved_binary_attribute_beats_candidate_reclassification(self):
        (self.repo / BINARY).write_bytes(b'\x00\xffpayload\n')
        fixture.write(self.repo, '.gitattributes', BINARY + ' text\n')
        fixture.commit(self.repo, 'Modify only line endings and reclassify the fixture')
        self.stale()

    def test_only_line_endings_in_committed_text_change_oracle_identity(self):
        for path in (HELPER, ORACLE):
            with self.subTest(path=path):
                content = (self.repo / path).read_text(encoding='utf-8')
                (self.repo / path).write_bytes(content.replace('\n', '\r\n').encode('utf-8'))
                # Store raw bytes regardless of the host's checkout configuration.
                oid = self.git('hash-object', '-w', '--no-filters', path)
                self.assertNotEqual(oid, self.git('rev-parse', 'HEAD:' + path))
                self.git('update-index', '--cacheinfo', '100644,' + oid + ',' + path)
                self.git('commit', '-qm', 'Store different bytes in an inventoried text blob')
                self.stale()
                self.git('reset', '--hard', self.refs['closed'])

    def test_git_replace_cannot_hide_a_modified_auxiliary(self):
        original = self.git('rev-parse', 'HEAD:' + HELPER)
        fixture.write(self.repo, HELPER, 'EXPECTED = 8\n')
        fixture.commit(self.repo, 'Change the auxiliary after verification')
        changed = self.git('rev-parse', 'HEAD:' + HELPER)
        self.git('replace', changed, original)
        self.assertEqual(self.git('show', 'HEAD:' + HELPER), 'EXPECTED = 7')
        self.stale()

    def test_dirty_helper_and_unrelated_commit_do_not_affect_projection(self):
        fixture.write(self.repo, 'note.md', 'unrelated\n')
        fixture.commit(self.repo, 'Change unrelated file')
        fixture.write(self.repo, HELPER, 'EXPECTED = 9\n')
        result = self.trace()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
