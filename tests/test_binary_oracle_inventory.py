"""Binary fixture bytes must not be normalized as text."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import guard_pr_baseline
from validation_runtime import prepare_runtime
from tests import test_oracle_inventory as inventory
from tests import test_contract_acceptance as acceptance


class BinaryInventory(unittest.TestCase):
    def fixture(self, kind):
        prepare_runtime()
        fixture = kind()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        contract = fixture.root / 'knowledge/contracts/task.md'
        text = contract.read_text(encoding='utf-8')
        import re
        text = re.sub(r'^(oracle_files: .*?)\]', r"\1, 'fixture.bin']", text, flags=re.M)
        contract.write_text(text, encoding='utf-8')
        (fixture.root / '.gitattributes').write_text('fixture.bin -text\n', encoding='utf-8')
        (fixture.root / 'fixture.bin').write_bytes(b'AA\r\n')
        return fixture

    def test_local_baseline_rejects_binary_newline_mutation(self):
        fixture = self.fixture(inventory.ApprovedInventory)
        fixture.commit()
        fixture.approved = fixture.git('rev-parse', 'HEAD')
        self.assertEqual(fixture.baseline(), [])
        (fixture.root / 'fixture.bin').write_bytes(b'AA\n')
        self.assertTrue(any('fixture.bin' in item for item in fixture.baseline()))

    def test_pr_baseline_rejects_binary_newline_mutation(self):
        fixture = self.fixture(inventory.ApprovedInventory)
        fixture.commit()
        approved = fixture.git('rev-parse', 'HEAD')
        (fixture.root / 'fixture.bin').write_bytes(b'AA\n')
        (fixture.root / '.gitattributes').write_text('fixture.bin text\n', encoding='utf-8')
        fixture.commit()
        candidate = fixture.git('rev-parse', 'HEAD')
        with patch.object(guard_pr_baseline, '_git', lambda *args: subprocess.check_output(
                ['git', '-C', str(fixture.root), *args], stderr=subprocess.PIPE)):
            self.assertTrue(any('fixture.bin' in item for item in
                                guard_pr_baseline.check(approved, candidate, approved)))

    def test_acceptance_rejects_binary_newline_mutation(self):
        fixture = self.fixture(acceptance.AcceptanceTests)
        fixture.freeze()
        self.assertTrue(fixture.verify()['ok'])
        (fixture.root / 'fixture.bin').write_bytes(b'AA\n')
        result = fixture.verify()
        self.assertFalse(result['ok'], result)
        self.assertIn('fixture.bin', result['error'])

    def test_nul_bytes_are_exact_even_without_attributes(self):
        from oracle_inventory import oracle_equal
        self.assertFalse(oracle_equal(b'\x00\n', b'\x00\r\n'))
