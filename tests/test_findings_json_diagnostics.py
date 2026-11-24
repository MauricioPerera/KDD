"""Integration coverage for format errors at the findings CLI boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = {
    "accessibility": "validate_accessibility_findings.py",
    "compliance": "validate_compliance_findings.py",
    "dependency-eol": "validate_dependency_eol_findings.py",
    "observability": "validate_observability_findings.py",
    "privacy": "validate_privacy_findings.py",
}
PRECHECK_DOMAINS = (*VALIDATORS, "security", "test-coverage")


class FindingsJsonDiagnostics(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kdd-findings-json-")
        self.addCleanup(temporary.cleanup)
        self.scan = Path(temporary.name)
        self.evidence = self.scan / "findings.json"

    def run_cli(self, name, *args, env=None):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "scripts" / name), *args],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
            timeout=30, check=False,
        )

    def validate(self, domain, body):
        self.evidence.write_bytes(body)
        result = self.run_cli(VALIDATORS[domain], str(self.scan))
        self.assertEqual(self.evidence.read_bytes(), body)
        return result

    def assert_format_error(self, result, code):
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 2, output)
        self.assertIn(f"[{code}]", output)
        self.assertNotIn("Traceback", output)

    def test_real_cli_reject_non_object_roots(self):
        for domain in VALIDATORS:
            for body in (b"[]", b"null", b'"text"'):
                with self.subTest(domain=domain, body=body):
                    self.assert_format_error(self.validate(domain, body), "DOCUMENT_TYPE")

    def test_truncated_findings_report_parse_error(self):
        for domain in VALIDATORS:
            with self.subTest(domain=domain):
                self.assert_format_error(self.validate(domain, b'{"findings": ['), "PARSE_ERROR")

    def test_valid_empty_findings_keep_policy_outcome(self):
        for domain in VALIDATORS:
            with self.subTest(domain=domain):
                body = json.dumps({"documentType": f"kdd-{domain}.findings", "findings": []})
                result = self.validate(domain, body.encode("utf-8"))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("0 finding(s)", result.stdout)

    def test_existing_document_and_policy_checks_continue_to_run(self):
        for domain in VALIDATORS:
            with self.subTest(domain=domain):
                self.assert_format_error(
                    self.validate(domain, b'{"documentType":"another-domain","findings":[]}'),
                    "DOCUMENT_TYPE",
                )
                body = json.dumps({"documentType": f"kdd-{domain}.findings", "findings": [{}]})
                violated = self.validate(domain, body.encode("utf-8"))
                self.assertEqual(violated.returncode, 1, violated.stdout + violated.stderr)
                self.assertIn("FAIL:", violated.stdout)

    def precheck(self, body, domain="privacy"):
        self.evidence.write_bytes(body)
        variable = "KDD_" + domain.upper().replace("-", "_") + "_SCAN_DIR"
        env = dict(os.environ, KDD_REQUIRED_EVIDENCE="")
        env[variable] = str(self.scan)
        result = self.run_cli("optional_evidence.py", "check", "--layers", domain, env=env)
        self.assertEqual(self.evidence.read_bytes(), body)
        return result

    def test_optional_precheck_rejects_non_json_constants(self):
        for domain in PRECHECK_DOMAINS:
            for constant in (b"NaN", b"Infinity", b"-Infinity"):
                with self.subTest(domain=domain, constant=constant):
                    prefix = "codex" if domain == "security" else "kdd"
                    kind = f"{prefix}-{domain}.findings".encode("utf-8")
                    body = b'{"documentType":"' + kind + b'","findings":[],"score":' + constant + b"}"
                    result = self.precheck(body, domain)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(f"FAIL [{domain}]", result.stdout)
                    self.assertIn("invalid evidence JSON", result.stdout)

    def test_optional_precheck_preserves_finite_numbers_and_optional_compatibility(self):
        for body in (
            b'{"documentType":"kdd-privacy.findings","findings":[],"score":1.5}',
            b'{"documentType":"kdd-privacy.findings","findings":[],"score":1,"score":2}',
        ):
            with self.subTest(body=body):
                result = self.precheck(body)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PRESENT [privacy]", result.stdout)


if __name__ == "__main__":
    unittest.main()
