"""Exercise the regression proof from Git objects and real unittest processes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


CLI = Path(__file__).resolve().parents[1] / "scripts" / "prove_regression.py"
PROBE = "tests/test_feature.py"
EXPECTED = "tests.test_feature.Feature.test_value"
NEIGHBOR = "tests.test_feature.Feature.test_neighbor"
TEST = '''
import os
import unittest
from pathlib import Path
import feature
from tests.helper import expected

class Feature(unittest.TestCase):
    def test_value(self):
        stamp = Path(__file__).resolve().parents[1] / 'attempt-stamp'
        self.assertFalse(stamp.exists(), 'attempt reused a working directory')
        stamp.touch()
        trace = os.environ.get('KDD_PROOF_TEST_CWD_LOG')
        if trace:
            with Path(trace).open('a', encoding='utf-8') as stream:
                stream.write(str(Path.cwd().resolve()) + '\\n')
        self.assertEqual(feature.value(), expected)

    def test_neighbor(self):
        self.assertTrue(feature.neighbor())
'''


def behavior(value="old", neighbor=True):
    return f"def value(): return {value!r}\ndef neighbor(): return {neighbor!r}\n"


class RegressionProof(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="kdd-proof-oracle-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "source repo"
        self.root.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.upper().startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "core.autocrlf", "false")
        self.write("tests/__init__.py", "")
        self.write("tests/helper.py", "expected = 'new'\n")
        sha = hashlib.sha256(TEST.encode("utf-8")).hexdigest()
        self.write("knowledge/contracts/feature.md", f"""---
task: feature
tests: {PROBE}
tests_sha256: {sha}
oracle_files: ['{PROBE}', 'tests/helper.py', 'tests/__init__.py']
test_runner: python-unittest
test_command: 'python -m unittest tests.test_feature'
test_timeout: 4
---
""")
        self.write(PROBE, TEST)
        self.write("feature.py", behavior())
        self.base = self.commit("broken implementation with sealed oracle")

    def write(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.encode("utf-8"))

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args],
                                       env=self.env, timeout=20)

    def commit(self, subject):
        self.git("add", "--", ".")
        self.git("commit", "-qm", subject)
        return self.git("rev-parse", "HEAD").decode("ascii").strip()

    def candidate(self, source=None):
        self.write("feature.py", behavior("new") if source is None else source)
        return self.commit("candidate")

    def replace_oracle(self, source):
        contract = self.root / "knowledge/contracts/feature.md"
        body = contract.read_text(encoding="utf-8")
        self.write(PROBE, source)
        self.write("knowledge/contracts/feature.md", body.replace(
            hashlib.sha256(TEST.encode()).hexdigest(), hashlib.sha256(source.encode()).hexdigest()))

    def prove(self, candidate, *, base=None, expected=EXPECTED, code=0):
        expected = [expected] if isinstance(expected, str) else expected
        selection = [arg for item in expected for arg in ("--expect-failure", item)]
        completed = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(CLI),
             "--repo-root", str(self.root), "--base", base or self.base,
             "--candidate", candidate, "--contract", "feature", *selection],
            env=self.env, capture_output=True, encoding="utf-8", timeout=35)
        codes = code if isinstance(code, tuple) else (code,)
        self.assertIn(completed.returncode, codes, completed.stdout + completed.stderr)
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError:
            self.fail("CLI did not emit a JSON receipt: " + completed.stderr)
        self.assertEqual(len(report["attempts"]), 0 if completed.returncode == 2 else 4)
        return report

    def test_proves_the_same_cases_from_commits_in_four_fresh_copies(self):
        candidate = self.candidate()
        trace = self.root.parent / "attempt-directories"
        self.env["KDD_PROOF_TEST_CWD_LOG"] = str(trace)
        self.write(PROBE, "raise RuntimeError('uncommitted oracle')\n")
        self.write("feature.py", "raise RuntimeError('uncommitted source')\n")
        dirty = self.git("status", "--porcelain=v1", "-z")
        report = self.prove(candidate)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "proven")
        self.assertEqual((report["base_commit"], report["candidate_commit"]), (self.base, candidate))
        self.assertEqual(report["oracle_sha256"][PROBE], hashlib.sha256(TEST.encode()).hexdigest())
        self.assertEqual([(item["side"], item["number"], item["status"]) for item in report["attempts"]],
                         [("base", 1, "assertion_failure"), ("base", 2, "assertion_failure"),
                          ("candidate", 1, "passed"), ("candidate", 2, "passed")])
        for item in report["attempts"]:
            self.assertCountEqual(item["case_ids"], [EXPECTED, NEIGHBOR])
            self.assertEqual(item["failed_cases"], [EXPECTED] if item["side"] == "base" else [])
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), candidate)
        self.assertEqual(self.git("status", "--porcelain=v1", "-z"), dirty)
        self.assertFalse((self.root / "attempt-stamp").exists())
        directories = trace.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(directories), 4)
        self.assertEqual(len(set(directories)), 4)
        self.assertFalse(any(Path(name).is_relative_to(self.root.resolve()) for name in directories))

    def test_expected_id_does_not_accept_a_different_assertion(self):
        report = self.prove(self.candidate(), expected=NEIGHBOR, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["attempts"][0]["failed_cases"], [EXPECTED])

    def test_unexpected_named_assertion_also_blocks(self):
        self.write("feature.py", behavior(neighbor=False))
        base = self.commit("two failing assertions")
        report = self.prove(self.candidate(), base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertCountEqual(report["attempts"][0]["failed_cases"], [EXPECTED, NEIGHBOR])

    def test_accepts_two_explicit_expected_failures(self):
        self.write("feature.py", behavior(neighbor=False))
        base = self.commit("two expected failures")
        report = self.prove(self.candidate(), base=base, expected=[EXPECTED, NEIGHBOR])
        self.assertEqual(report["status"], "proven")
        for attempt in report["attempts"][:2]:
            self.assertCountEqual(attempt["failed_cases"], [EXPECTED, NEIGHBOR])

    def test_import_error_on_base_is_not_a_reproduced_regression(self):
        self.write("feature.py", "raise ImportError('fixture runtime failure')\n")
        base = self.commit("broken runtime")
        report = self.prove(self.candidate(), base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["attempts"][0]["status"], "inconclusive")
        self.assertEqual(report["attempts"][0]["failed_cases"], [])

    def test_skipped_candidate_is_inconclusive(self):
        source = "import unittest\ndef value(): raise unittest.SkipTest('omitted')\ndef neighbor(): return True"
        report = self.prove(self.candidate(source), code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["attempts"][2]["status"], "inconclusive")

    def test_runtime_error_reported_as_failure_is_not_an_assertion(self):
        self.replace_oracle(TEST + "\nFeature.failureException = RuntimeError\n")
        base = self.commit("unittest labels runtime errors as failures")
        report = self.prove(self.candidate(), base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["attempts"][0]["status"], "inconclusive")
        self.assertEqual(report["attempts"][0]["failed_cases"], [])

    def test_expected_failure_marker_is_inconclusive(self):
        self.replace_oracle(TEST + "\nFeature.test_value = unittest.expectedFailure(Feature.test_value)\n")
        base = self.commit("expected failure decorator")
        report = self.prove(self.candidate(), base=base, code=1)
        self.assertEqual(report["attempts"][0]["status"], "inconclusive")

    def test_selected_module_without_cases_is_inconclusive(self):
        contract = self.root / "knowledge/contracts/feature.md"
        body = contract.read_text(encoding="utf-8")
        self.write("knowledge/contracts/feature.md", body.replace(
            "unittest tests.test_feature'", "unittest tests.test_feature tests.helper'"))
        base = self.commit("declared invocation contains module without cases")
        report = self.prove(self.candidate(), base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["attempts"][2]["status"], "inconclusive")

    def test_a_green_retry_does_not_erase_the_first_candidate_failure(self):
        counter = self.root.parent / "candidate-count"
        self.env["KDD_PROOF_TEST_COUNTER"] = str(counter)
        candidate = self.candidate(textwrap.dedent("""\
            import os
            from pathlib import Path
            def value():
                counter = Path(os.environ['KDD_PROOF_TEST_COUNTER'])
                if counter.exists():
                    return 'new'
                counter.touch()
                return 'old'
            def neighbor(): return True
            """))
        report = self.prove(candidate, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual([item["status"] for item in report["attempts"][2:]],
                         ["assertion_failure", "passed"])

    def test_oracle_helper_drift_is_rejected_before_running_either_side(self):
        self.write("tests/helper.py", "expected = 'old'\n")
        report = self.prove(self.candidate(), code=2)
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["attempts"], [])

    def test_unsealed_identical_oracle_is_rejected(self):
        self.write(PROBE, TEST + "\n# changed after sealing\n")
        base = self.commit("oracle with a stale seal")
        report = self.prove(self.candidate(), base=base, code=2)
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["attempts"], [])

    def test_symbolic_base_is_rejected(self):
        report = self.prove(self.candidate(), base="HEAD", code=2)
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["attempts"], [])

    def test_git_replace_does_not_change_the_original_baseline(self):
        candidate = self.candidate()
        self.git("replace", self.base, candidate)
        report = self.prove(candidate)
        self.assertEqual(report["attempts"][0]["failed_cases"], [EXPECTED])
        self.assertEqual(report["base_commit"], self.base)

    def test_case_id_cannot_link_different_runtime_methods(self):
        self.replace_oracle(TEST + "\nFeature.test_value = feature.check\n")
        old = behavior() + "def check(self): self.assertEqual('old', 'new')\n"
        self.write("feature.py", old)
        base = self.commit("same test ID assigned to a different callable")
        candidate = self.candidate(behavior("new") + "def check(self): self.assertEqual('new', 'new')\n")
        report = self.prove(candidate, base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertCountEqual(report["attempts"][2]["case_ids"], [EXPECTED, NEIGHBOR])

    def test_partialmethod_with_changed_arguments_is_inconclusive(self):
        self.replace_oracle(TEST + """
from functools import partialmethod
def check(self, actual):
    self.assertEqual(actual, expected)
Feature.test_value = partialmethod(check, feature.value())
""")
        base = self.commit("bound argument from broken implementation")
        report = self.prove(self.candidate(), base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")

    def test_closure_with_changed_expectation_is_inconclusive(self):
        self.replace_oracle(TEST + """
def make_case(want):
    def check(self):
        self.assertEqual(feature.value(), want)
    return check
Feature.test_value = make_case(feature.expectation())
""")
        self.write("feature.py", behavior() + "def expectation(): return 'new'\n")
        base = self.commit("broken value with original expectation")
        candidate = self.candidate(behavior() + "def expectation(): return 'old'\n")
        report = self.prove(candidate, base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")

    def test_default_with_changed_expectation_is_inconclusive(self):
        self.replace_oracle(TEST + """
def check(self, want=feature.expectation()):
    self.assertEqual(feature.value(), want)
Feature.test_value = check
""")
        self.write("feature.py", behavior() + "def expectation(): return 'new'\n")
        base = self.commit("broken value with original default expectation")
        candidate = self.candidate(behavior() + "def expectation(): return 'old'\n")
        report = self.prove(candidate, base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")

    def test_successful_subtest_also_makes_attempt_inconclusive(self):
        self.replace_oracle(TEST.replace("        self.assertTrue(feature.neighbor())",
            "        with self.subTest(name='neighbor'):\n"
            "            self.assertTrue(feature.neighbor())"))
        base = self.commit("oracle with a successful subtest")
        report = self.prove(self.candidate(), base=base, code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["attempts"][2]["status"], "inconclusive")

    def test_export_ignore_cannot_yield_a_partial_snapshot(self):
        self.write(".gitattributes", "feature.py export-ignore\n")
        report = self.prove(self.candidate(), code=(0, 2))
        self.assertEqual(report["status"], "proven" if report["attempts"] else "invalid")

    def test_export_subst_cannot_create_the_apparent_fix(self):
        self.write(".gitattributes", "feature.py export-subst\n")
        self.write("feature.py", behavior("$Format:%s$"))
        base = self.commit("old")
        self.write("note.txt", "unrelated change\n")
        candidate = self.commit("new")
        report = self.prove(candidate, base=base, code=(1, 2))
        if report["attempts"]:
            self.assertEqual(report["status"], "inconclusive")
            self.assertTrue(all(item["failed_cases"] == [EXPECTED] for item in report["attempts"]))
        else:
            self.assertEqual(report["status"], "invalid")

    def test_local_grafts_do_not_make_siblings_ancestors(self):
        self.write("feature.py", behavior("other old value"))
        sibling = self.commit("sibling")
        self.git("switch", "--detach", self.base)
        candidate = self.candidate()
        self.write(".git/info/grafts", f"{candidate} {sibling}\n")
        report = self.prove(candidate, base=sibling, code=2)
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["attempts"], [])

    def test_timeouts_are_inconclusive(self):
        source = "import time\ndef value():\n    time.sleep(8)\n    return 'new'\ndef neighbor(): return True"
        report = self.prove(self.candidate(source), code=1)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual([item["status"] for item in report["attempts"][2:]],
                         ["inconclusive", "inconclusive"])


if __name__ == "__main__":
    unittest.main()
