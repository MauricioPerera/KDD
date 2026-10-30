"""Adversarial regressions for the complete, approved oracle inventory."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from oracle_inventory import inventory_paths
from validate_baseline import validate_baseline
import guard_pr_baseline


class InventorySchema(unittest.TestCase):
    def test_explicit_inventory_includes_oracle_and_support_files(self):
        self.assertEqual(inventory_paths({'tests': 'tests/oracle.py',
                                         'oracle_files': ['fixture.json', 'tests/oracle.py', 'helper.py']}),
                         ['fixture.json', 'helper.py', 'tests/oracle.py'])

    def test_legacy_requires_explicit_acceptance_migration(self):
        self.assertEqual(inventory_paths({'tests': 'oracle.py'}), ['oracle.py'])
        with self.assertRaisesRegex(ValueError, 'inventory'):
            inventory_paths({'tests': 'oracle.py'}, required=True)

    def test_invalid_inventories_fail_closed(self):
        bad = [[], 'oracle.py', ['helper.py'], ['oracle.py', 'oracle.py'],
               ['oracle.py', 'ORACLE.py'], ['oracle.py', '../helper.py'],
               ['oracle.py', '/helper.py'], ['oracle.py', 'C:/helper.py'],
               ['oracle.py', 'helper*.py'], ['oracle.py', 'a/./helper.py'],
               ['oracle.py', 'a\\helper.py'], ['oracle.py', ''],
               ['oracle.py', 'a//helper.py'], ['oracle.py', None]]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                inventory_paths({'tests': 'oracle.py', 'oracle_files': value})


class ApprovedInventory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.write('knowledge/contracts/task.md',
                   "---\ntests: oracle.py\noracle_files: ['oracle.py', 'helper.py', 'fixture.json', 'runner.json']\n---\n")
        self.write('target.py', 'VALUE = 1\n')
        self.write('oracle.py', 'from helper import verify\nverify()\n')
        self.write('helper.py', 'from target import VALUE\ndef verify():\n    assert VALUE == 1\n')
        self.write('fixture.json', '{"expected": 1}\n')
        self.write('runner.json', '{"mode": "strict"}\n')
        self.commit()
        self.approved = self.git('rev-parse', 'HEAD')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
                                       stderr=subprocess.STDOUT, text=True).strip()

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Inventory Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'fixture')

    def baseline(self):
        return validate_baseline('knowledge/contracts/task.md', self.approved, self.root)

    def test_approved_and_implementation_only_change(self):
        self.assertEqual(self.baseline(), [])
        self.write('target.py', 'VALUE = 2\n')
        self.assertEqual(self.baseline(), [])

    def test_neutralized_helper_cannot_hide_bad_implementation(self):
        self.write('target.py', 'VALUE = 0\n')
        failing = subprocess.run([sys.executable, 'oracle.py'], cwd=self.root,
                                 capture_output=True, timeout=5)
        self.assertNotEqual(failing.returncode, 0)
        self.write('helper.py', 'def verify():\n    pass\n')
        passing = subprocess.run([sys.executable, 'oracle.py'], cwd=self.root,
                                 capture_output=True, timeout=5)
        self.assertEqual(passing.returncode, 0)
        self.assertTrue(any('helper.py' in item for item in self.baseline()))

    def test_fixture_config_deletion_and_contract_resigning_rejected(self):
        for name in ('fixture.json', 'runner.json'):
            old = (self.root / name).read_bytes()
            self.write(name, '{}\n')
            self.assertTrue(any(name in item for item in self.baseline()))
            (self.root / name).write_bytes(old)
        (self.root / 'helper.py').unlink()
        self.assertTrue(any('helper.py' in item for item in self.baseline()))
        self.write('knowledge/contracts/task.md', '---\ntests: oracle.py\n---\n')
        self.assertTrue(any('task.md' in item for item in self.baseline()))

    def test_pr_gate_reads_inventory_from_approved_commit(self):
        self.write('helper.py', 'def verify():\n    pass\n')
        self.commit()
        candidate = self.git('rev-parse', 'HEAD')
        original = guard_pr_baseline._git
        try:
            guard_pr_baseline._git = lambda *args: subprocess.check_output(
                ['git', '-C', str(self.root), *args], stderr=subprocess.PIPE)
            findings = guard_pr_baseline.check(self.approved, candidate, self.approved)
        finally:
            guard_pr_baseline._git = original
        self.assertTrue(any('helper.py' in item for item in findings))

    def test_missing_approved_inventory_file_rejected(self):
        self.write('knowledge/contracts/task.md',
                   "---\ntests: oracle.py\noracle_files: ['oracle.py', 'missing.py']\n---\n")
        self.commit()
        with self.assertRaises(ValueError):
            validate_baseline('knowledge/contracts/task.md', self.git('rev-parse', 'HEAD'), self.root)


if __name__ == '__main__':
    unittest.main()
