"""Regression oracle for the commit message gate's JSON length setting."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_commit_message import main


class CommitMessageLengthConfigTest(unittest.TestCase):
    def run_gate(self, value):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({
                "types": ["feat"],
                "max_subject_length": value,
            }), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                code = main([str(config), "--message", "feat: a change"])
            return code, output.getvalue()

    def test_rejects_invalid_lengths_without_raising(self):
        for value in (None, "72", 72.5, True, False, -1, [], {}):
            with self.subTest(value=value):
                code, output = self.run_gate(value)
                self.assertEqual(code, 1)
                self.assertIn("ERROR [CONFIG_INVALID]", output)
                self.assertIn("max_subject_length", output)

    def test_zero_keeps_the_warning_only_behavior(self):
        code, output = self.run_gate(0)
        self.assertEqual(code, 0)
        self.assertIn("WARNING [SUBJECT_TOO_LONG]", output)

    def test_valid_length_keeps_success(self):
        code, output = self.run_gate(72)
        self.assertEqual(code, 0)
        self.assertIn("0 error(es), 0 warning(s)", output)
