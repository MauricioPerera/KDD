"""Execute the validators through their real CLI with isolated inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ValidatorCliInputs(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kdd-validator-cli-")
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name)
        self.contract = self.sandbox / "fixture.md"
        self.contract.write_text(
            "---\ntouch_only: ['src/inside.py']\ntests: 'tests/fixture.py'\n---\n",
            encoding="utf-8",
        )

    def execute(self, command, *args, stdin=""):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "scripts" / command), *args],
            cwd=ROOT, input=stdin, capture_output=True, text=True, encoding="utf-8",
            timeout=35, check=False,
        )

    def test_perimeter_typo_reports_the_option(self):
        result = self.execute("validate_perimeter.py", str(self.contract), "--change", "src/outside.py")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, r"(?<![\w-])--change(?![\w-])")
        self.assertNotIn("0 archivo(s) cambiados", output)

    def test_perimeter_stdin_and_changed_keep_the_same_result(self):
        by_stdin = self.execute("validate_perimeter.py", str(self.contract), stdin="src/outside.py\n")
        by_option = self.execute("validate_perimeter.py", str(self.contract), "--changed", "src/outside.py")
        self.assertEqual((by_stdin.returncode, by_option.returncode), (1, 1))
        self.assertEqual(by_stdin.stdout, by_option.stdout)
        self.assertIn("OUT_OF_PERIMETER", by_stdin.stdout)
        self.assertIn("src/outside.py", by_stdin.stdout)
        good = self.execute("validate_perimeter.py", str(self.contract), "--changed", "src/inside.py")
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)

    def test_missing_and_empty_contract_options_are_not_validation(self):
        for flag in ("--hash", "--repo-root"):
            for tail in ((), ("",)):
                with self.subTest(flag=flag, tail=tail):
                    result = self.execute("validate_contracts.py", flag, *tail)
                    output = result.stdout + result.stderr
                    self.assertEqual(result.returncode, 1, output)
                    self.assertIn(flag, output)
                    self.assertNotIn("todos los contratos son validos", output)

    def test_missing_option_value_is_rejected_even_with_valid_hash_input(self):
        evidence = self.sandbox / "oracle.py"
        evidence.write_bytes(b"fixture\n")
        digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
        invalid = (
            ("--repo-root", ("--hash", str(evidence), "--repo-root")),
            ("--repo-root", ("--repo-root", "--hash", str(evidence))),
            ("--hash", ("--hash", "--repo-root", str(ROOT))),
        )
        for missing, args in invalid:
            with self.subTest(args=args):
                result = self.execute("validate_contracts.py", *args)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 1, output)
                self.assertIn(missing, output)
                self.assertNotIn(digest, output)
                self.assertNotIn("Resumen:", output)

    def test_contract_options_keep_hash_and_explicit_validation(self):
        payload = b"test evidence\n"
        evidence = self.sandbox / "oracle.py"
        evidence.write_bytes(payload)
        result = self.execute("validate_contracts.py", "--hash", str(evidence))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), hashlib.sha256(payload).hexdigest())
        contract = ROOT / "knowledge" / "contracts" / "perimeter-gate.md"
        result = self.execute("validate_contracts.py", "--repo-root", str(ROOT), str(contract))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 archivo(s)", result.stdout)

    def commit_message(self, types):
        config = self.sandbox / "commit.json"
        config.write_text(json.dumps({"types": types, "max_subject_length": 72}), encoding="utf-8")
        return self.execute("validate_commit_message.py", str(config), "--message", "fix: adjust text")

    def test_commit_message_rejects_invalid_types_config(self):
        for types in ("fix", {"fix": True}, None, ["fix", 1]):
            with self.subTest(types=types):
                result = self.commit_message(types)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 1, output)
                self.assertIn("CONFIG_INVALID", output)
                self.assertNotIn("Traceback", output)

    def test_commit_message_valid_config_keeps_type_selection(self):
        allowed = self.commit_message(["fix"])
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        excluded = self.commit_message(["feat"])
        self.assertEqual(excluded.returncode, 1, excluded.stdout + excluded.stderr)
        self.assertIn("TYPE_UNKNOWN", excluded.stdout)


if __name__ == "__main__":
    unittest.main()
