"""Independent real-Git checks for batch and explicit oracle inventories."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.test_fixture_preparation import configure_git

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/validate_baseline.py'


class BatchInventoryIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kdd inventory batch ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q', '-b', 'main')
        configure_git(self.root, {'user.name': 'Inventory Test', 'user.email': 'inventory@example.invalid',
            'core.autocrlf': 'false'}, ephemeral=True)
        (self.root / 'knowledge/contracts').mkdir(parents=True)
        (self.root / 'tests').mkdir()
        (self.root / '.gitattributes').write_text('tests/fixture.bin -text\n', encoding='utf8')
        (self.root / 'knowledge/contracts/task.md').write_text(
            "---\ntests: 'tests/oracle.py'\noracle_files: ['tests/oracle.py', "
            "'tests/helper.py', 'tests/fixture.bin']\n---\n", encoding='utf8')
        (self.root / 'tests/oracle.py').write_bytes(b'# oracle\n')
        (self.root / 'tests/helper.py').write_bytes(b'# helper\n')
        (self.root / 'tests/fixture.bin').write_bytes(b'line one\r\nline two\r\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'approved')
        self.ref = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        p = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True,
                           text=True, encoding='utf8', timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def check(self, all_contracts):
        mode = ['--all'] if all_contracts else ['knowledge/contracts/task.md']
        bootstrap = ("import os,runpy,sys; from pathlib import Path; "
                     "script=sys.argv.pop(1); sys.path.insert(0,os.environ.get('KDD_BATCH_IMPORT_DIR',str(Path(script).parent))); "
                     "sys.argv[0]=script; runpy.run_path(script,run_name='__main__')")
        return subprocess.run([sys.executable, '-I', '-c', bootstrap, str(SOURCE), *mode,
            '--repo-root', str(self.root), '--approved-ref', self.ref],
            capture_output=True, text=True, encoding='utf8', timeout=120)

    def assert_both(self, expected, marker):
        for all_contracts in (False, True):
            with self.subTest(all_contracts=all_contracts):
                p = self.check(all_contracts)
                self.assertEqual(p.returncode, expected, p.stdout + p.stderr)
                self.assertIn(marker, p.stdout)

    def test_approved_inventory_passes(self):
        self.assert_both(0, 'PASS:')

    def test_changed_helper_is_detected(self):
        (self.root / 'tests/helper.py').write_bytes(b'# mutated\n')
        self.assert_both(1, 'tests/helper.py: differs')

    def test_binary_without_nul_still_compares_exactly(self):
        (self.root / 'tests/fixture.bin').write_bytes(b'line one\nline two\n')
        self.assert_both(1, 'tests/fixture.bin: differs')

    def test_missing_helper_is_detected(self):
        (self.root / 'tests/helper.py').unlink()
        self.assert_both(1, 'tests/helper.py: approved artifact missing')

    def test_git_symlink_in_approved_inventory_is_rejected(self):
        oid = self.git('rev-parse', 'HEAD:tests/helper.py').strip()
        self.git('update-index', '--add', '--cacheinfo', '120000,' + oid + ',tests/helper.py')
        self.git('commit', '-qm', 'invalid symlink inventory')
        self.ref = self.git('rev-parse', 'HEAD').strip()
        self.assert_both(2, 'missing or not regular')


if __name__ == '__main__':
    unittest.main(verbosity=2)
