"""Run adopt_project.py against a Git origin and audit its lock writes."""
import json
import unittest

from tests.adoption_remediation_support import AdoptionIntegration, MANAGED


class AdoptionPinTests(AdoptionIntegration, unittest.TestCase):
    def test_nonexistent_pin_is_rejected_before_plan_or_write(self):
        before = self.fixture.snapshot()
        for mode in ("--plan", "--apply"):
            with self.subTest(mode=mode):
                run = self.installer(mode, pin="f" * 40)
                self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                self.assertIn("ADOPTION_PIN", run.stderr)
                self.assertEqual(self.fixture.snapshot(), before)
                self.assertEqual(self.git("status", "--porcelain"), "")

    def test_preview_update_and_rollback_only_change_the_lock(self):
        self.install()
        self.commit("Install KDD at A")
        old_files = self.fixture.snapshot()
        for old, new in ((self.first, self.second), (self.second, self.first)):
            with self.subTest(old=old, new=new):
                options = ("--expected-validator-commit", old)
                before = self.fixture.snapshot()
                plan = self.installer("--plan", pin=new, options=options)
                self.assertEqual(plan.returncode, 0, plan.stdout + plan.stderr)
                self.assertEqual(json.loads(plan.stdout)["update"], [".kdd/validator.lock"])
                self.assertEqual(self.fixture.snapshot(), before)
                apply = self.installer(pin=new, options=options)
                self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
                self.assertEqual(json.loads(apply.stdout)["update"], [".kdd/validator.lock"])
                self.assertEqual(self.git("diff", "--cached", "--name-only"), "")
                for path in set(MANAGED) - {".kdd/validator.lock"}:
                    self.assertEqual((self.root / path).read_bytes(), old_files[path])
                execution = self.launch()
                self.assertEqual(execution.returncode, 0, execution.stdout + execution.stderr)
                self.assertEqual(self.evidence(execution)["verified_kdd_sha"], new)
        self.assertEqual(self.fixture.snapshot(), old_files)

    def test_stale_expected_pin_preserves_bytes_and_index(self):
        self.install()
        self.commit("Install KDD at A")
        before = self.fixture.snapshot()
        run = self.installer(pin=self.second, options=("--expected-validator-commit", self.second))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("ADOPTION_CONFLICT", run.stderr)
        self.assertEqual(self.fixture.snapshot(), before)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_explicit_update_requires_complete_installation(self):
        self.write(".kdd/validator.lock", (self.first + "\n").encode("ascii"))
        before = self.fixture.snapshot()
        run = self.installer(pin=self.second, options=("--expected-validator-commit", self.first))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("ADOPTION_CONFLICT", run.stderr)
        self.assertEqual(self.fixture.snapshot(), before)
