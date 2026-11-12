"""Exercise the installed review entry point against an existing Git project."""

import json
import shutil
import subprocess
import unittest

from tests.adoption_remediation_support import AdoptionIntegration, ROOT


class PluginOddEgmReviewTests(AdoptionIntegration, unittest.TestCase):
    def setUp(self):
        super().setUp()
        shutil.copyfile(ROOT / "scripts/baseline_review.py", self.seed / "scripts/baseline_review.py")
        self.seed_git("add", "scripts/baseline_review.py")
        self.seed_git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                      "-c", "commit.gpgsign=false", "commit", "-qm", "Reviewed pin")
        self.first = self.seed_git("rev-parse", "HEAD")
        self.install()
        self.write("README.md", b"# Label projet\n")
        self.approved = self.commit("Approve the installation in the existing project")

    def seed_git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.seed), *args],
                                       encoding="utf-8", timeout=30).strip()

    def review(self, candidate, *args, approved=None):
        return self.invoke("entry", self.root / ".kdd/validate.py", (
            "review", "--approved-ref", self.approved if approved is None else approved,
            "--base-ref", self.approved, "--candidate-ref", candidate, *args,
        ))

    def result(self, process, code=0):
        self.assertEqual(process.returncode, code, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertNotIn("approved_ref", result)
        self.assertEqual(result["verified_kdd_sha"], self.first)
        return result

    def editorial_candidate(self):
        self.write("README.md", b"# Label project\n")
        return self.commit("Fix a typo")

    def guarantee_candidate(self):
        contract = "knowledge/contracts/label.md"
        self.write(contract, (self.root / contract).read_bytes().replace(
            b"Strip spaces.", b"Strip leading and trailing spaces."))
        return contract, self.commit("Clarify a guarantee in the protected contract")

    def review_record(self, candidate, path, status):
        return {
            "schema_version": 1,
            "base_commit": self.approved,
            "candidate_commit": candidate,
            "candidate_tree": self.git("rev-parse", candidate + "^{tree}"),
            "author": "author",
            "risk": "high",
            "risk_rationale": "The candidate changes an existing contract.",
            "risk_factors": [],
            "reviews": [{
                "id": f"review-{index}", "reviewer": f"reader-{index}",
                "kind": "agent", "fresh_context": True, "status": status,
                "lenses": [{"name": lens, "assessment": "pass", "rationale": "Read the contract."}
                           for lens in ("simplicity", "oracle", "implementation")]
                if status == "completed" else [],
                "read_set": [{"revision": "candidate", "path": path}]
                if status == "completed" else [],
            } for index in (1, 2)],
            "findings": [],
        }

    def write_record(self, record):
        file = self.root.parent / "review record.json"
        file.write_text(json.dumps(record), encoding="utf-8")
        return "../" + file.name

    def test_editorial_confirmation_uses_the_same_pin_as_terminal_validation(self):
        candidate = self.editorial_candidate()
        terminal = self.invoke("entry", self.root / ".kdd/validate.py")
        self.assertEqual(terminal.returncode, 0, terminal.stdout + terminal.stderr)
        pending = self.result(self.review(candidate, "--small-change"))
        eligible = self.result(self.review(candidate, "--small-change", "--editorial-only"))
        self.assertEqual((pending["route"], pending["reason"]), ("standard", "confirmation_required"))
        self.assertEqual((eligible["route"], eligible["reason"]), ("lightweight", "editorial_only"))
        self.assertEqual(eligible["verified_kdd_sha"], self.evidence(terminal)["verified_kdd_sha"])
        self.assertEqual(eligible["candidate_commit"], candidate)
        self.assertFalse(eligible["review_ready"])

    def test_guarantee_change_routes_to_standard_even_with_editorial_confirmation(self):
        path, candidate = self.guarantee_candidate()
        inspected = self.result(self.review(candidate, "--small-change", "--editorial-only"))
        self.assertEqual((inspected["route"], inspected["risk_floor"]), ("standard", "high"))
        self.assertEqual([item["path"] for item in inspected["changes"]], [path])
        self.assertFalse(inspected["review_ready"])

    def test_unavailable_reviewers_leave_the_baseline_pending(self):
        path, candidate = self.guarantee_candidate()
        record = self.write_record(self.review_record(candidate, path, "not_run"))
        pending = self.result(self.review(candidate, "--review", record), code=1)
        self.assertFalse(pending["review_ready"])
        self.assertIn("REVIEW_INCOMPLETE", {item["code"] for item in pending["findings"]})

    def test_complete_review_is_bound_to_the_exact_candidate_tree(self):
        path, candidate = self.guarantee_candidate()
        record = self.review_record(candidate, path, "completed")
        file = self.write_record(record)
        verdict = self.result(self.review(candidate, "--review", file))
        self.assertTrue(verdict["review_ready"])
        self.assertEqual(verdict["candidate_tree"], record["candidate_tree"])
        self.assertEqual(verdict["required_reviewers"], 2)
        different = self.editorial_candidate()
        rejected = self.review(different, "--review", file)
        self.assertEqual(rejected.returncode, 2, rejected.stdout + rejected.stderr)
        self.assertIn("REVIEW_IDENTITY", rejected.stderr)
        self.assertEqual(rejected.stdout, "")

    def test_review_reads_another_ref_without_writing_or_executing_it(self):
        self.git("checkout", "-qb", "proposal")
        self.write("product.py", b"raise RuntimeError('candidate executed')\n")
        candidate = self.commit("Candidate with code that must not run")
        self.git("checkout", "-q", "main")
        marker = self.root.parent / "oracle-executed"
        self.write("scripts/baseline_review.py", (
            b"import os\nfrom pathlib import Path\n"
            b"Path(os.environ['KDD_ADOPTION_TEST_SENTINEL']).write_text('untrusted reviewer')\n"
        ))
        before = (self.fixture.snapshot(), self.git("show-ref"), self.git("ls-files", "--stage"),
                  self.git("config", "--local", "--list"))
        report = self.result(self.review(candidate))
        self.assertEqual(report["candidate_commit"], candidate)
        self.assertEqual(report["changes"][0]["path"], "product.py")
        self.assertFalse(marker.exists(), "Review executed consumer code")
        after = (self.fixture.snapshot(), self.git("show-ref"), self.git("ls-files", "--stage"),
                 self.git("config", "--local", "--list"))
        self.assertEqual(before, after)

    def test_rejects_a_different_local_pin_and_a_relative_reference(self):
        candidate = self.editorial_candidate()
        relative = self.review(candidate, approved="HEAD")
        self.assertEqual(relative.returncode, 2, relative.stdout + relative.stderr)
        self.assertIn("KDD_ADOPTION_APPROVED_REF", relative.stderr)
        self.write(".kdd/validator.lock", (self.second + "\n").encode("ascii"))
        replaced = self.review(candidate)
        self.assertEqual(replaced.returncode, 2, replaced.stdout + replaced.stderr)
        self.assertIn(".kdd/validator.lock", replaced.stderr)
        self.assertEqual(replaced.stdout, "")

    def test_pin_without_the_reviewer_requires_an_explicit_upgrade(self):
        self.write(".kdd/validator.lock", (self.second + "\n").encode("ascii"))
        self.approved = self.commit("Approve the older pin without baseline_review")
        candidate = self.editorial_candidate()
        result = self.review(candidate)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("baseline_review.py", result.stderr)
        self.assertIn("upgrade", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
