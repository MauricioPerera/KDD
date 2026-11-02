"""Missing instruments must remain visible as failed obligation rows."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_contract_acceptance as fixtures


class MissingMatrix(unittest.TestCase):
    def test_missing_check_keeps_complete_matrix_with_explicit_failure(self):
        fixture = fixtures.AcceptanceTests()
        fixture.setUp()
        try:
            fixture.policy['contracts'][0]['checks'] = [
                check for check in fixture.policy['contracts'][0]['checks']
                if check['obligation'] != 'signature']
            fixture.freeze()
            result = fixture.verify()
            self.assertFalse(result['ok'])
            rows = result['contracts'][0]['obligations']
            row = next(row for row in rows if row['obligation'] == 'signature')
            self.assertEqual(row['status'], 'FAIL')
            self.assertTrue(row['evidence'])
            self.assertEqual(len(rows), 8)
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
