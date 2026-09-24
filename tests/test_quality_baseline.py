import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import quality_baseline


class QualityBaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "KDD Test"], cwd=self.root, check=True)
        (self.root / "quality.json").write_text(json.dumps({
            "protected": ["tests/oracle.txt"],
            "implementation": ["src/app.py"],
            "pm": ["quality.json"],
            "required_kinds": ["functional", "adversarial"],
            "checks": [
                {"name": "functional", "kind": "functional", "argv": ["python", "-V"], "timeout": 10},
                {"name": "adversarial", "kind": "adversarial", "argv": ["python", "-V"], "timeout": 10},
            ],
        }))
        (self.root / "tests").mkdir()
        (self.root / "tests" / "oracle.txt").write_text("frozen\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("print('ok')\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.root, check=True)
        self.ref = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_contains_explicit_ref_and_protected_hashes(self):
        result = quality_baseline.build_baseline(self.root, "quality.json", self.ref)
        self.assertEqual(result["approved_ref"], self.ref)
        self.assertEqual(result["protected"]["tests/oracle.txt"]["sha256"],
                         "9c45da1b799a603c167323bd7ed4f52034ec28ea5e04373045a9c11f1ddc5446")
        self.assertIn("policy_sha256", result)

    def test_missing_explicit_ref_is_rejected(self):
        with self.assertRaises(quality_baseline.Rejected):
            quality_baseline.build_baseline(self.root, "quality.json", "HEAD~99")


if __name__ == "__main__":
    unittest.main()
