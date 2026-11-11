"""Exercise validate.py with a policy approved before candidate changes."""
import unittest

from tests.adoption_remediation_support import AdoptionIntegration, POLICY


class ApprovedAdoptionQualityTests(AdoptionIntegration, unittest.TestCase):
    def approved_quality(self, name=POLICY, helper=True):
        self.install()
        self.policy(name, helper)
        return self.commit("Approve the consumer policy and oracles")

    def check_quality(self, approved, success):
        run = self.launch({"KDD_QUALITY_APPROVED_REF": approved})
        record = self.evidence(run)
        self.assertEqual(run.returncode, 0 if success else 1, run.stdout + run.stderr)
        self.assertEqual(record["stage"], "complete" if success else "quality")
        if success:
            self.assertEqual(record["quality_approved_ref"], approved)
            self.assertIn("PASS quality: integrity, perimeter and all checks verified twice", run.stdout)
            self.assertEqual(record["executed_tests"], 1)
        else:
            self.assertNotIn("executed_tests", record)
            self.assertFalse((self.root.parent / "oracle-executed").exists())
        return run

    def test_approved_product_policy_executes_twice(self):
        self.check_quality(self.approved_quality(), True)

    def test_approved_legacy_name_executes_twice(self):
        self.check_quality(self.approved_quality("quality.json"), True)

    def test_staged_and_committed_deletion_cannot_turn_quality_off(self):
        approved = self.approved_quality()
        self.git("rm", "--", POLICY)
        self.check_quality(approved, False)
        self.commit("Remove policy from candidate")
        self.check_quality(approved, False)

    def test_restored_worktree_does_not_hide_policy_deletion_from_head(self):
        approved = self.approved_quality()
        original = (self.root / POLICY).read_bytes()
        self.git("rm", "--", POLICY)
        self.commit("Remove policy from candidate")
        self.write(POLICY, original)
        self.git("add", "--", POLICY)
        self.check_quality(approved, False)

    def test_approved_reference_without_policy_fails(self):
        self.install()
        approved = self.commit("Consumer without a quality policy")
        self.check_quality(approved, False)

    def test_ambiguous_approved_policy_fails_even_after_candidate_removes_one(self):
        self.install()
        self.policy()
        self.policy("quality.json")
        approved = self.commit("Ambiguous approval candidate")
        self.git("rm", "--", "quality.json")
        self.commit("Select one policy without review")
        run = self.check_quality(approved, False)
        self.assertIn("ambiguous", (run.stdout + run.stderr).lower())

    def test_adoption_baseline_preserves_quality_requirement_without_quality_ref(self):
        approved = self.approved_quality()
        self.git("rm", "--", POLICY)
        self.commit("Remove the quality policy before PR validation")
        run = self.launch({"KDD_ADOPTION_APPROVED_REF": approved})
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["stage"], "quality")
        self.assertIn("KDD_QUALITY_APPROVED_REF", run.stdout + run.stderr)
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_historical_missing_helper_remains_a_quality_failure(self):
        run = self.check_quality(self.approved_quality(helper=False), False)
        self.assertIn("scripts/process_tree.py", run.stdout + run.stderr)
