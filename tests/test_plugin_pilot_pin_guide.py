"""Keep the released validator pin separate from pilot prerequisites."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE_PIN = "144168d168410c28315f07d53e87638a4a10b81c"
README = "plugins/kdd-codex/README.md"


def section(path, heading):
    text = (ROOT / path).read_text(encoding="utf-8")
    return " ".join(text.split("## " + heading + "\n", 1)[1].split("\n## ", 1)[0].split())


class PluginPilotPinGuideTests(unittest.TestCase):
    def test_release_guide_keeps_the_versioned_pin_and_count_evidence(self):
        release = section(README, "Upgrade an existing Python project")
        self.assertIn(f"/blob/{RELEASE_PIN}/tools/kdd-adoption/README.md", release)
        self.assertIn("`verified_kdd_sha`", release)
        self.assertIn("two `oracle_passes` counts", release)
        self.assertIn("ODD/EGM pilot", release)

    def test_pilot_entry_points_require_a_compatible_launcher_and_reviewed_pin(self):
        for path, heading in (
            (README, "Review in an adopted project"),
            ("plugins/kdd-codex/skills/kdd-workflow/SKILL.md", "Review a change in an adopted project"),
            ("tools/kdd-adoption/README.md", "Review a change"),
        ):
            with self.subTest(path=path):
                pilot = section(path, heading)
                self.assertIn("compatible launcher", pilot)
                self.assertIn("reviewed validator pin", pilot)
                self.assertIn("bound-method receipts", pilot)
