"""Tests for optional evidence classification used by CI summaries."""

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import optional_evidence as optional  # noqa: E402


class OptionalEvidenceTests(unittest.TestCase):
    def test_absent_optional_scan_is_skip(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {'KDD_SECURITY_SCAN_DIR': temp,
                   'KDD_SECURITY_OUTCOME': 'success'}
            row = optional.evaluate_layers(['security'], set(), env, True)[0]
            self.assertEqual(row['status'], 'SKIP')

    def test_failed_validator_never_becomes_skip(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {'KDD_SECURITY_SCAN_DIR': temp,
                   'KDD_SECURITY_OUTCOME': 'failure'}
            row = optional.evaluate_layers(['security'], set(), env, True)[0]
            self.assertEqual(row['status'], 'FAIL')

    def test_absent_required_scan_fails_before_validator(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {'KDD_SECURITY_SCAN_DIR': temp}
            row = optional.evaluate_layers(['security'], {'security'}, env)[0]
            self.assertEqual(row['status'], 'FAIL')

    def test_present_file_is_not_pass_before_validator(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'findings.json').write_text('{}', encoding='utf-8')
            env = {'KDD_SECURITY_SCAN_DIR': temp}
            row = optional.evaluate_layers(['security'], set(), env)[0]
            self.assertEqual(row['status'], 'PRESENT')

    def test_present_and_success_is_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'findings.json').write_text('{}', encoding='utf-8')
            env = {'KDD_SECURITY_SCAN_DIR': temp,
                   'KDD_SECURITY_OUTCOME': 'success'}
            row = optional.evaluate_layers(['security'], set(), env, True)[0]
            self.assertEqual(row['status'], 'PASS')

    def test_present_but_failed_or_skipped_is_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'findings.json').write_text('{}', encoding='utf-8')
            for outcome in ('failure', 'skipped', ''):
                with self.subTest(outcome=outcome):
                    env = {'KDD_SECURITY_SCAN_DIR': temp,
                           'KDD_SECURITY_OUTCOME': outcome}
                    row = optional.evaluate_layers(['security'], set(), env, True)[0]
                    self.assertEqual(row['status'], 'FAIL')

    def test_quality_uses_policy_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, 'quality.json')
            env = {'KDD_QUALITY_POLICY': str(path),
                   'KDD_QUALITY_OUTCOME': 'success'}
            self.assertEqual(optional.evaluate_layers(['quality'], set(), env, True)[0]
                             ['status'], 'SKIP')
            path.write_text('{}', encoding='utf-8')
            self.assertEqual(optional.evaluate_layers(['quality'], set(), env, True)[0]
                             ['status'], 'PASS')

    def test_unknown_and_out_of_scope_required_names_fail(self):
        with self.assertRaises(ValueError):
            optional._names('security,unrecognized')
        with self.assertRaises(ValueError):
            optional.evaluate_layers(['security'], {'quality'}, {}, True)

    def test_markdown_escapes_untrusted_path(self):
        table = optional._markdown([{'layer': 'security', 'status': 'SKIP',
                                     'source': 'a|b', 'reason': 'missing'}])
        self.assertIn('a\\|b', table)


if __name__ == '__main__':
    unittest.main()
