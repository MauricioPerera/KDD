"""Exercise approval and editorial boundaries through the installed launcher."""

from copy import deepcopy
import json
import sys
import unittest

import yaml

from tests import test_adoption_trusted_pr as trusted
from tests import test_plugin_odd_egm_review as review


class AdversarialReviewTests(unittest.TestCase):
    def setUp(self):
        self.consumer = review.PluginOddEgmReviewTests()
        self.addCleanup(self.consumer.doCleanups)
        self.consumer.setUp()
        path = self.consumer.root / ".github/workflows/kdd-validate.yml"
        self.consumer.workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    def run_step(self, approved):
        return trusted.TrustedAdoptionPullRequestTests.run_step(self.consumer, approved)

    def assert_rejected(self, result, code, message):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertIn(message, result.stdout + result.stderr)

    def test_a01_reference_must_be_an_exact_ancestor_commit(self):
        consumer = self.consumer
        candidate = consumer.editorial_candidate()
        consumer.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                     "tag", "-a", "review-tag", "-m", "Review tag", consumer.approved)
        tag = consumer.git("rev-parse", "refs/tags/review-tag")
        consumer.git("checkout", "-qb", "unrelated")
        consumer.write("other.txt", b"Unrelated revision\n")
        unrelated = consumer.commit("Other history")
        consumer.git("checkout", "--detach", candidate)
        for invalid, reason in (
            ("", "approved"), ("HEAD", "approved"), (consumer.approved[:12], "approved"),
            (tag, "exact"), (unrelated, "ancestor"),
        ):
            with self.subTest(invalid=invalid):
                inspection = consumer.review(candidate, approved=invalid)
                self.assert_rejected(inspection, 2, reason)
                self.assertEqual(inspection.stdout, "")
                self.assert_rejected(self.run_step(invalid), 1, reason)
                self.assertFalse((consumer.root.parent / "oracle-executed").exists())

    def test_a02_index_and_hidden_worktree_changes_cannot_replace_the_pin(self):
        consumer = self.consumer
        candidate = consumer.editorial_candidate()
        lock = ".kdd/validator.lock"
        alternate = (consumer.second + "\n").encode("ascii")
        consumer.write(lock, alternate)
        consumer.git("add", "--", lock)
        consumer.write(lock, (consumer.first + "\n").encode("ascii"))
        self.assert_rejected(consumer.review(candidate), 2, lock)
        self.assert_rejected(self.run_step(consumer.approved), 1, lock)
        consumer.git("restore", "--staged", "--", lock)
        consumer.git("update-index", "--assume-unchanged", "--", lock)
        consumer.write(lock, alternate)
        self.assertEqual(consumer.git("status", "--porcelain"), "")
        self.assert_rejected(consumer.review(candidate), 2, lock)
        self.assert_rejected(self.run_step(consumer.approved), 1, lock)
        self.assertFalse((consumer.root.parent / "oracle-executed").exists())

    def test_a03_external_git_and_python_inputs_do_not_substitute_the_review(self):
        consumer = self.consumer
        candidate = consumer.editorial_candidate()
        expected = consumer.result(consumer.review(candidate))
        consumer.git("checkout", "-qb", "replacement")
        consumer.write("product.py", b"raise RuntimeError('candidate should not execute')\n")
        replacement = consumer.commit("Replacement with executable code")
        consumer.git("checkout", "--detach", candidate)
        consumer.git("replace", candidate, replacement)
        marker = consumer.root.parent / "isolation-breached"
        payload = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        consumer.write("decoy/json.py", payload.encode("utf-8"))
        consumer.write("decoy/diff.py", payload.encode("utf-8"))
        consumer.git("config", "diff.external", f'"{sys.executable}" "{consumer.root / "decoy/diff.py"}"')
        before = (consumer.fixture.snapshot(), consumer.git("show-ref"), consumer.git("ls-files", "--stage"),
                  consumer.git("config", "--local", "--list"))
        process = consumer.invoke("entry", consumer.root / ".kdd/validate.py", (
            "review", "--approved-ref", consumer.approved, "--base-ref", consumer.approved,
            "--candidate-ref", candidate,
        ), settings={"GIT_DIR": str(consumer.seed / ".git"), "PYTHONPATH": str(consumer.root / "decoy")})
        self.assertEqual(consumer.result(process), expected)
        self.assertFalse(marker.exists())
        self.assertEqual((consumer.fixture.snapshot(), consumer.git("show-ref"),
                          consumer.git("ls-files", "--stage"), consumer.git("config", "--local", "--list")),
                         before)

    def test_a05_mixed_and_restored_changes_stay_on_the_standard_route(self):
        consumer = self.consumer
        for path in ("tests/test_product.py", "knowledge/contracts/label.md", ".github/workflows/extra.yml"):
            with self.subTest(path=path):
                consumer.git("checkout", "--detach", consumer.approved)
                file = consumer.root / path
                original = file.read_bytes() if file.is_file() else b"name: Extra\non: push\n"
                consumer.write(path, original + b"\n# New guarantee\n")
                candidate = consumer.editorial_candidate()
                result = consumer.result(consumer.review(candidate, "--small-change", "--editorial-only"))
                self.assertEqual((result["route"], result["reason"]), ("standard", "outside_scope"))
        consumer.git("checkout", "--detach", consumer.approved)
        product = (consumer.root / "product.py").read_bytes()
        consumer.write("product.py", product + b"\n# Intermediate change\n")
        consumer.commit("Intermediate code change")
        consumer.write("product.py", product)
        candidate = consumer.editorial_candidate()
        result = consumer.result(consumer.review(candidate, "--small-change", "--editorial-only"))
        self.assertEqual([change["path"] for change in result["changes"]], ["README.md"])
        self.assertEqual((result["route"], result["reason"]), ("standard", "history"))

    def test_a06_a_semantic_readme_change_requires_editorial_confirmation(self):
        consumer = self.consumer
        obligation = "Validation must compare every case ID per contract."
        consumer.write("README.md", ("# Label project\n\n" + obligation + "\n").encode("utf-8"))
        candidate = consumer.commit("Document a new validation obligation")
        self.assertIn("+" + obligation, consumer.git("diff", consumer.approved, candidate, "--", "README.md"))
        result = consumer.result(consumer.review(candidate, "--small-change"))
        self.assertEqual((result["route"], result["reason"]), ("standard", "confirmation_required"))

    def test_a07_review_rejects_replayed_identity_and_ambiguous_json(self):
        consumer = self.consumer
        path, candidate = consumer.guarantee_candidate()
        good = consumer.review_record(candidate, path, "completed")
        tree = good["candidate_tree"]
        other = consumer.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                             "commit-tree", tree, "-p", consumer.approved, "-m", "Distinct commit")
        self.assertNotEqual(candidate, other)
        self.assertEqual(consumer.git("rev-parse", other + "^{tree}"), tree)
        file = consumer.write_record(good)
        self.assert_rejected(consumer.review(other, "--review", file), 2, "REVIEW_IDENTITY")
        file = consumer.write_record(dict(good, candidate_tree="0" * len(tree)))
        self.assert_rejected(consumer.review(candidate, "--review", file), 2, "REVIEW_IDENTITY")
        (consumer.root / file).write_text('{"risk":"low",' + json.dumps(good)[1:], encoding="utf-8")
        result = consumer.review(candidate, "--review", file)
        self.assert_rejected(result, 2, "REVIEW_SCHEMA")
        self.assertEqual(result.stdout, "")

    def test_a08_incomplete_or_conflicted_review_is_pending(self):
        consumer = self.consumer
        path, candidate = consumer.guarantee_candidate()
        good = consumer.review_record(candidate, path, "completed")
        author = deepcopy(good)
        author["reviews"][1]["reviewer"] = good["author"]
        missing = deepcopy(good)
        for reader in missing["reviews"]:
            reader["lenses"] = reader["lenses"][:1]
            reader["read_set"] = []
        invalid = dict(good, findings=[{
            "id": "F1", "severity": "major", "status": "accepted", "scope": path,
            "rationale": "Agent attempted to accept residual risk.",
            "decided_by": good["reviews"][0]["reviewer"],
            "evidence": [{"revision": "candidate", "path": path}],
        }])
        for record, reason in (
            (dict(good, risk="low"), "RISK_TOO_LOW"), (author, "REVIEW_INDEPENDENCE"),
            (missing, "LENS_MISSING"), (missing, "SOURCE_COVERAGE"), (invalid, "DECISION_INVALID"),
        ):
            with self.subTest(reason=reason):
                report = consumer.result(consumer.review(candidate, "--review", consumer.write_record(record)), code=1)
                self.assertFalse(report["review_ready"])
                self.assertIn(reason, {item["code"] for item in report["findings"]})
        repeated = deepcopy(good)
        repeated["reviews"][1]["reviewer"] = repeated["reviews"][0]["reviewer"]
        self.assert_rejected(
            consumer.review(candidate, "--review", consumer.write_record(repeated)), 2, "REVIEW_SCHEMA"
        )

    def test_a09_review_ready_cannot_supply_an_adoption_approval(self):
        consumer = self.consumer
        path, candidate = consumer.guarantee_candidate()
        good = consumer.review_record(candidate, path, "completed")
        file = consumer.write_record(good)
        before = (consumer.fixture.snapshot(), consumer.git("show-ref"), consumer.git("ls-files", "--stage"),
                  consumer.git("config", "--local", "--list"))
        self.assertTrue(consumer.result(consumer.review(candidate, "--review", file))["review_ready"])
        self.assertEqual((consumer.fixture.snapshot(), consumer.git("show-ref"),
                          consumer.git("ls-files", "--stage"), consumer.git("config", "--local", "--list")), before)
        self.assert_rejected(self.run_step(""), 1, "KDD_ADOPTION_APPROVED_REF")
        self.assertFalse((consumer.root.parent / "oracle-executed").exists())
        file = consumer.write_record(dict(good, approved_ref=consumer.approved))
        self.assert_rejected(consumer.review(candidate, "--review", file), 2, "REVIEW_SCHEMA")
