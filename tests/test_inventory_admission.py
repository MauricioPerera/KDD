"""Inventory admission is separate from historical single-file contracts."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_contracts import validate_file, _calculate_tests_hash


class InventoryAdmission(unittest.TestCase):
    def test_contract_symlink_cannot_select_a_different_approved_contract(self):
        import subprocess
        from validation_runtime import prepare_runtime
        from validate_baseline import validate_baseline
        prepare_runtime()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'oracle.py').write_text('assert True\n')
            text = '---\ntests: oracle.py\n---\n'
            (root / 'task.md').write_text(text)
            (root / 'other.md').write_text(text)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args],
                                               stderr=subprocess.STDOUT, text=True).strip()
            git('init', '-q')
            git('add', '.')
            git('-c', 'user.name=Inventory Test', '-c', 'user.email=test@example.invalid',
                'commit', '-qm', 'approved')
            reference = git('rev-parse', 'HEAD')
            original_resolve, original_symlink = Path.resolve, Path.is_symlink
            def resolve(path, *args, **kwargs):
                return root / 'other.md' if path == root / 'task.md' else original_resolve(path, *args, **kwargs)
            def symlink(path):
                return path == root / 'task.md' or original_symlink(path)
            # Simulate a link even on hosts without link-creation privileges.
            with patch.object(Path, 'resolve', resolve), patch.object(Path, 'is_symlink', symlink):
                with self.assertRaises(ValueError):
                    validate_baseline('task.md', reference, root)

    def test_inventory_schema_existence_and_perimeter_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'oracle.py').write_text('assert True\n')
            (root / 'helper.py').write_text('EXPECTED = 1\n')
            (root / 'target.py').write_text('VALUE = 1\n')
            template = (Path(__file__).resolve().parents[1] /
                        'knowledge/contracts/oracle-inventory.md').read_text(encoding='utf-8')
            import re
            template = re.sub(r'^target:.*$', 'target: target.py', template, flags=re.M)
            template = re.sub(r'^tests:.*$', 'tests: oracle.py', template, flags=re.M)
            template = re.sub(r'^tests_sha256:.*$', 'tests_sha256: ' +
                              _calculate_tests_hash(root / 'oracle.py'), template, flags=re.M)
            template = re.sub(r'^touch_only:.*$', "touch_only: ['target.py']", template, flags=re.M)
            contract = root / 'task.md'
            def findings(value, touches=None):
                text = re.sub(r'^oracle_files:.*$', 'oracle_files: ' + value, template, flags=re.M)
                if touches:
                    text = text.replace("touch_only: ['target.py']", touches)
                contract.write_text(text, encoding='utf-8')
                return [str(item) for item in validate_file(contract, root)]
            self.assertEqual(findings("['oracle.py', 'helper.py']"), [])
            for value in ("[]", "['helper.py']", "['oracle.py', '../helper.py']",
                          "['oracle.py', 'missing.py']"):
                with self.subTest(value=value):
                    self.assertTrue(findings(value))
            self.assertTrue(findings("['oracle.py', 'helper.py']",
                                     "touch_only: ['target.py', 'helper.py']"))


if __name__ == '__main__':
    unittest.main()
