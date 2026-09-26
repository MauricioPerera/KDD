"""Public Pages source selection and artifact safeguards."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


BUILD = Path(__file__).resolve().parents[1] / "site/build.py"
spec = importlib.util.spec_from_file_location("kdd_pages_build", BUILD)
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


class PagesBuildTests(unittest.TestCase):
    def test_only_allowlisted_tracked_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            for name in ("knowledge/spec.md", "docs/reports/CONTRACT-1-REPORT.md",
                         ".agents/AGENTS.md", ".agents/logs/secret.txt", "README.md"):
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("example", encoding="utf-8")
            subprocess.run(["git", "add", "-f", "."], cwd=repo, check=True)
            self.assertEqual(
                sorted(str(path).replace("\\", "/") for path in pages.tracked_public_files(repo)),
                [".agents/AGENTS.md", "docs/reports/CONTRACT-1-REPORT.md", "knowledge/spec.md"],
            )

    def test_manifest_prefix_is_idempotent(self):
        manifest = {"published": [{"url": "/skills/a", "tool_url": "/KDD/skills/a.js"}],
                    "memory": {"snapshot_url": "/skills-index.snapshot"}}
        self.assertEqual(pages.prefix_manifest(pages.prefix_manifest(manifest)),
                         {"published": [{"url": "/KDD/skills/a", "tool_url": "/KDD/skills/a.js"}],
                          "memory": {"snapshot_url": "/KDD/skills-index.snapshot"}})

    def test_landing_counts_and_ci_evidence(self):
        html = ''.join(f'<span class="n" id="{name}">old</span>'
                       for name in ("report-count", "gate-count", "test-count"))
        html += '<a id="ci-evidence-link" href="old">CI</a>'
        actual = pages.update_landing(html, 33, 18, 844,
                                      "https://github.com/MauricioPerera/KDD/actions/runs/123")
        for value in ("33", "18", "844", "/actions/runs/123"):
            self.assertIn(value, actual)
        with self.assertRaises(ValueError):
            pages.update_landing("", 1, 2, 3, "x")

    def test_rejects_foreign_ci_url_and_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                pages.build_pages(str(root), str(root / "new"), "https://example.com/run/1")
            with self.assertRaises(FileExistsError):
                pages.build_pages(str(root), str(root),
                                  "https://github.com/MauricioPerera/KDD/actions/runs/1")
            with self.assertRaises(ValueError):
                pages.build_pages(str(root), str(root / "inside"),
                                  "https://github.com/MauricioPerera/KDD/actions/runs/1")


if __name__ == "__main__":
    unittest.main()
