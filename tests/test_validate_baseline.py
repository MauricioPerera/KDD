import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_baseline import validate_baseline, validate_all_baselines


class BaselineTests(unittest.TestCase):
    def test_resealed_test_and_contract_are_rejected_against_approved_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.STDOUT, text=True).strip()
            git('init')
            oracle = root / 'oracle.py'
            oracle.write_text('assert 1 == 1\n', encoding='utf-8')
            contract = root / 'task.md'
            def seal():
                contract.write_text("---\ntests: 'oracle.py'\ntests_sha256: '" + hashlib.sha256(oracle.read_bytes()).hexdigest() + "'\n---\n", encoding='utf-8')
            seal()
            git('add', '.')
            git('-c', 'user.name=Audit', '-c', 'user.email=audit@example.invalid', 'commit', '-m', 'approved oracle')
            approved = git('rev-parse', 'HEAD')
            self.assertEqual(validate_baseline('task.md', approved, root), [])
            oracle.write_text('assert True\n', encoding='utf-8')
            seal()
            findings = validate_baseline('task.md', approved, root)
            self.assertEqual(len(findings), 2)
            self.assertTrue(any('oracle.py' in f for f in findings))
            self.assertTrue(any('task.md' in f for f in findings))

    def test_invalid_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                validate_baseline('../outside.md', 'not-a-commit', root)

    def test_all_rejects_resealed_oracle_and_contract_additions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts = root / 'knowledge' / 'contracts'
            contracts.mkdir(parents=True)
            oracle = root / 'product_tests' / 'test_app.py'
            oracle.parent.mkdir()
            oracle.write_text('assert 1 == 1\n', encoding='utf-8')
            contract = contracts / 'app.md'
            def seal():
                contract.write_text("---\ntests: 'product_tests/test_app.py'\ntests_sha256: '" +
                                    hashlib.sha256(oracle.read_bytes()).hexdigest() + "'\n---\n",
                                    encoding='utf-8')
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args],
                                               stderr=subprocess.STDOUT, text=True).strip()
            git('init')
            seal()
            git('add', '.')
            git('-c', 'user.name=Audit', '-c', 'user.email=audit@example.invalid',
                'commit', '-m', 'approved')
            approved = git('rev-parse', 'HEAD')
            self.assertEqual(validate_all_baselines(approved, root), [])
            oracle.write_text('assert True\n', encoding='utf-8')
            seal()
            findings = validate_all_baselines(approved, root)
            self.assertEqual(len(findings), 2)
            (contracts / 'new.md').write_text(contract.read_text(encoding='utf-8'), encoding='utf-8')
            findings = validate_all_baselines(approved, root)
            self.assertTrue(any('new.md: not in approved reference' in f for f in findings))
            contract.unlink()
            findings = validate_all_baselines(approved, root)
            self.assertTrue(any('app.md: approved contract missing' in f for f in findings))


if __name__ == '__main__':
    unittest.main()
