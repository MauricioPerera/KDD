"""Execute the generated PR step against independent consumer revisions."""
import hashlib
import os
from pathlib import Path
import shutil
import unittest

import yaml

from tests.adoption_remediation_support import AdoptionIntegration


class TrustedAdoptionPullRequestTests(AdoptionIntegration, unittest.TestCase):
    def setUp(self):
        super().setUp()
        path = "knowledge/contracts/label.md"
        contract = (self.root / path).read_bytes()
        self.write(path, contract.replace(b"oracle_files: ['tests/test_product.py']",
                                         b"oracle_files: ['tests/test_product.py', 'tests/__init__.py']"))
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
        self.assertEqual(step.get("shell"), "python -I {0}", "The PR step must isolate trusted extraction.")
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
        path = "tests/test_product.py"
        old = (self.root / path).read_bytes()
        append = b"            with Path(os.environ['KDD_ADOPTION_TEST_SENTINEL']).open('a') as marker:\n"
        new = old.replace(b"            Path(os.environ['KDD_ADOPTION_TEST_SENTINEL']).write_text('executed')\n",
                          append + b"                marker.write(str(os.getpid()) + '\\n')\n")
        self.assertNotEqual(old, new)
        self.write(path, new)
        contract = "knowledge/contracts/label.md"
        self.write(contract, (self.root / contract).read_bytes().replace(
            hashlib.sha256(old).hexdigest().encode(), hashlib.sha256(new).hexdigest().encode()))
        self.approved = self.commit("Approve an oracle with a mark per execution")
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
        marks = (self.root.parent / "oracle-executed").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(marks), 2)
        self.assertTrue(all(mark.isdecimal() for mark in marks), marks)
        self.assertEqual(len(set(marks)), 2)

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

    def test_independent_workflow_rejects_candidate_workflow_replacement(self):
        path = ".github/workflows/kdd-validate.yml"
        self.write(path, b"name: Candidate replacement\non: [pull_request]\n")
        self.commit("Replace the checkout copy of the workflow")
        run = self.run_step(self.approved)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(path, run.stdout + run.stderr)
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_candidate_cannot_modify_an_inventoried_helper(self):
        marker = self.root.parent / "modified-helper-ran"
        self.write("tests/__init__.py",
                   ("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n").encode())
        self.commit("Change the inventoried Python package initializer")
        run = self.run_step(self.approved)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("tests/__init__.py", run.stdout + run.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_candidate_git_executable_is_not_resolved_from_checkout(self):
        if os.name == "nt":
            system_tool = Path(os.environ["SystemRoot"]) / "System32/findstr.exe"
            shutil.copyfile(system_tool, self.root / "git.exe")
        else:
            self.write("git", b"#!/bin/sh\nprintf 'candidate git ran'\nexit 9\n")
            (self.root / "git").chmod(0o755)
        self.commit("Introduce a decoy Git executable in the candidate root")
        run = self.run_step(self.approved)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["verified_kdd_sha"], self.first)
        self.assertEqual(self.evidence(run)["oracle_passes"], [1, 1])

    def test_historical_free_command_is_rejected_before_execution(self):
        marker = self.root.parent / "free-command-ran"
        self.write("legacy_hook.py",
                   ("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n").encode())
        path = "knowledge/contracts/label.md"
        old = (self.root / path).read_bytes()
        updated = old.replace(b"test_runner: python-unittest\n", b"").replace(
            b"oracle_files: ['tests/test_product.py', 'tests/__init__.py']\n", b"").replace(
            b"python -m unittest tests/test_product.py", b"python legacy_hook.py")
        self.assertNotEqual(old, updated)
        self.write(path, updated)
        approved = self.commit("Register a historical unmanaged contract")
        run = self.run_step(approved)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("python-unittest", run.stdout + run.stderr)
        self.assertFalse(marker.exists())
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
