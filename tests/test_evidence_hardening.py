import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_security_findings as security
import preflight


class EvidenceHardening(unittest.TestCase):
    def run_security(self, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = security.main(args)
        return code, out.getvalue()

    def test_minimal_document_is_not_sealed_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'findings.json').write_text(json.dumps({
                'documentType': 'codex-security.findings', 'findings': []
            }), encoding='utf-8')
            code, output = self.run_security([root])
            self.assertNotEqual(code, 0)
            self.assertNotIn('Traceback', output)

    def test_required_scan_cannot_be_missing(self):
        with tempfile.TemporaryDirectory() as root:
            code, output = self.run_security([root, '--required'])
            self.assertNotEqual(code, 0)
            self.assertIn('PATH_MISSING', output)
            self.assertEqual(self.run_security([root])[0], 0)

    def test_malformed_top_level_is_a_data_error(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'findings.json').write_text('[]', encoding='utf-8')
            code, output = self.run_security([root])
            self.assertEqual(code, 2)
            self.assertNotIn('Traceback', output)

    def test_preflight_labels_missing_optional_evidence_as_skip(self):
        def runner(name, params, repo_root='.', timeout=120):
            return {'exit_code': 0, 'stdout': 'INFO [PATH_MISSING] no scan', 'stderr': ''}
        result = preflight.run_preflight(runner=runner)
        self.assertTrue(result['overall_ok'])
        self.assertTrue(any('SKIP' in line for line in result['lines']))
        self.assertFalse(any(': PASS' in line for line in result['lines']))


if __name__ == '__main__':
    unittest.main()
