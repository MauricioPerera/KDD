import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import bootstrap_project


class BootstrapProjectTests(unittest.TestCase):
    def test_dry_run_does_not_write_start_file(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(bootstrap_project, "init_project", return_value={
                "removed": [], "index_rewritten": False,
                "readme_renamed": False, "applied": False,
            }):
                result = bootstrap_project.bootstrap_project(root, False, "Demo", "minimal")
            self.assertFalse(result["applied"])
            self.assertFalse((Path(root) / "KDD-START-HERE.md").exists())
            self.assertIn("minimal", result["start_here"])

    def test_apply_composes_initializer_and_writes_onboarding(self):
        with tempfile.TemporaryDirectory() as root:
            init_result = {"removed": ["src/example.py"], "index_rewritten": True,
                           "readme_renamed": True, "applied": True}
            with mock.patch.object(bootstrap_project, "init_project", return_value=init_result) as init:
                result = bootstrap_project.bootstrap_project(root, True, "Demo", "standard")
            init.assert_called_once_with(root, True, "Demo")
            self.assertTrue(result["applied"])
            content = (Path(root) / "KDD-START-HERE.md").read_text(encoding="utf-8")
            self.assertIn("python scripts/run_profile.py --profile standard", content)
            self.assertIn("Demo", content)

    def test_rejects_unknown_profile(self):
        with self.assertRaises(ValueError):
            bootstrap_project.bootstrap_project(".", False, None, "unknown")


if __name__ == "__main__":
    unittest.main()
