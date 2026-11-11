"""Execute the generated PR step against independent consumer revisions."""
import hashlib
import unittest

import yaml

from tests.adoption_remediation_support import AdoptionIntegration


class TrustedAdoptionPullRequestTests(AdoptionIntegration, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.install()
        self.workflow = yaml.load((self.root / ".github/workflows/kdd-validate.yml").read_text(
            encoding="utf-8"), Loader=yaml.BaseLoader)
        self.approved = self.commit("Approve adoption files and product oracle")

    def test_workflow_has_read_only_pull_request_matrix(self):
        self.assertEqual(set(self.workflow["on"]), {"push", "pull_request", "workflow_dispatch"})
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        job = self.workflow["jobs"]["validate"]
        self.assertEqual(job["strategy"]["matrix"]["os"], ["ubuntu-latest", "windows-latest"])
        checkout = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["ref"], "\u0024{{ github.sha }}")
        self.assertEqual(checkout["with"]["persist-credentials"], "false")
        self.assertEqual(checkout["with"]["fetch-depth"], "0")
        self.assertNotIn("secrets.", str(self.workflow))

    def run_step(self, approved):
        steps = self.workflow["jobs"]["validate"]["steps"]
        step, = (step for step in steps if step.get("name") == "Validate the selected contracts")
        self.assertEqual(step.get("shell"), "python", "The PR step must run the trusted extraction.")
        self.assertEqual(step["env"]["KDD_ADOPTION_APPROVED_REF"], "\u0024{{ vars.KDD_ADOPTION_APPROVED_REF }}")
        self.assertNotIn("\u0024{{", step["run"])
        entry = self.root.parent / "workflow-step.py"
        entry.write_text(step["run"], encoding="utf-8")
        return self.invoke("workflow", entry, settings={
            "KDD_ADOPTION_APPROVED_REF": approved,
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_SHA": self.git("rev-parse", "HEAD"),
            "GITHUB_WORKSPACE": str(self.root),
            "RUNNER_TEMP": str(self.root.parent),
        })

    def test_approved_merge_candidate_runs_the_same_oracle_twice(self):
        self.git("checkout", "-qb", "change")
        self.write("product.py", b"def label(text):\n    return text.strip().casefold()\n")
        self.commit("Compatible product change")
        self.git("checkout", "-q", "main")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "merge", "-q", "--no-ff", "change")
        run = self.run_step(self.approved)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        evidence = self.evidence(run)
        self.assertEqual(evidence["consumer_sha"], self.git("rev-parse", "HEAD"))
        self.assertEqual(evidence["verified_kdd_sha"], self.first)
        self.assertEqual(evidence["executed_tests"], 1)
        self.assertEqual(evidence["oracle_passes"], [1, 1])
        self.assertEqual(run.stdout.count("oracle_execution: runner=python-unittest executed_tests=1"), 2)

    def test_pr_requires_approved_ref(self):
        for invalid in ("", "HEAD"):
            with self.subTest(invalid=invalid):
                run = self.run_step(invalid)
                self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_non_ancestor_approval_is_rejected(self):
        self.git("checkout", "-qb", "unrelated")
        self.write("review-note.txt", b"Reviewed for a different line.\n")
        unrelated = self.commit("Approval unrelated to the candidate")
        self.git("checkout", "-q", "main")
        run = self.run_step(unrelated)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("ancestor", (run.stdout + run.stderr).lower())
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_candidate_launcher_never_executes(self):
        marker = self.root.parent / "candidate-launcher-executed"
        self.write(".kdd/validate.py",
                   ("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n").encode())
        self.commit("Replace the candidate launcher")
        run = self.run_step(self.approved)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(".kdd/validate.py", run.stdout + run.stderr)
        self.assertFalse(marker.exists())

    def test_candidate_pin_cannot_select_another_runtime(self):
        self.write(".kdd/validator.lock", (self.second + "\n").encode("ascii"))
        self.commit("Replace the candidate pin")
        run = self.run_step(self.approved)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(".kdd/validator.lock", run.stdout + run.stderr)
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_resealed_regression_is_rejected_before_oracle_execution(self):
        self.write("product.py", b"def label(text):\n    return 'regression'\n")
        old = (self.root / "tests/test_product.py").read_bytes()
        new = old.replace(b"'demo')", b"'regression')")
        self.assertNotEqual(old, new)
        self.write("tests/test_product.py", new)
        path = "knowledge/contracts/label.md"
        contract = (self.root / path).read_bytes()
        updated = contract.replace(hashlib.sha256(old).hexdigest().encode(),
                                   hashlib.sha256(new).hexdigest().encode())
        self.assertNotEqual(contract, updated)
        self.write(path, updated)
        self.commit("Regress the product and adapt the oracle to hide it")
        run = self.run_step(self.approved)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("approved reference", run.stdout + run.stderr)
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_product_regression_with_unchanged_oracle_fails_in_oracle(self):
        self.write("product.py", b"def label(text):\n    return 'regression'\n")
        self.commit("Regress product only")
        run = self.run_step(self.approved)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["stage"], "oracle")
        self.assertIn("AssertionError", run.stdout + run.stderr)

    def test_nested_contract_does_not_change_the_selected_inventory(self):
        path = "knowledge/contracts/label.md"
        self.write("knowledge/contracts/nested/label.md", (self.root / path).read_bytes())
        self.write("knowledge/index.md", b"# Knowledge\n\n- [Label](contracts/label.md)\n"
                   b"- [Nested label](contracts/nested/label.md)\n")
        self.approved = self.commit("Approve an independent nested contract")
        run = self.run_step(self.approved)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["oracle_passes"], [1, 1])
