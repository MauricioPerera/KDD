"""Exercise the official timeout handoff without modifying its verdict."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import test_postinit_command_timing as command_timing
from tests import test_postinit_timeout_observation as worker

ROOT = worker.ROOT


class HostedProgress(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="kdd-ci-postinit-")
        self.addCleanup(temp.cleanup)
        self.area = Path(temp.name).resolve()
        self.private = self.area / "kdd-native-tests-fixture"
        self.project = self.private / "initialized"
        (self.project / "tests").mkdir(parents=True)
        self.marker = self.private / "kdd-postinit-project.json"
        self.output = self.area / "kdd-postinit-progress.json"
        self.env = dict(os.environ, TEMP=str(self.private), TMP=str(self.private),
                        TMPDIR=str(self.private), RUNNER_TEMP=str(self.area),
                        GITHUB_WORKSPACE=str(ROOT), GITHUB_RUN_ID="4321",
                        GITHUB_RUN_ATTEMPT="3", GITHUB_SHA="a"*40,
                        KDD_TRUSTED_RUNTIME_REF="b"*40)

    def run_python(self, arguments):
        return subprocess.run([sys.executable, "-I", *arguments], env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=25)

    def mark(self, project=None):
        script = ("import sys; sys.path.insert(0, sys.argv[1]);"
                  "from postinit_timeout_observation import mark_project;"
                  "raise SystemExit(0 if mark_project(sys.argv[2]) else 1)")
        return self.run_python(["-c", script, str(worker.COLLECTOR.parent),
                                str(self.project if project is None else project)])

    def require_marker(self):
        created = self.mark()
        self.assertEqual(created.returncode, 0, created.stderr)

    def collect(self, state):
        result = self.run_python([str(worker.COLLECTOR), "--ci-output"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(self.output.is_file(), result.stdout)
        report = json.loads(self.output.read_bytes())
        identity = {key: report[key] for key in report if key != "modules"}
        self.assertEqual(identity, dict(schema_version=1, run_id=self.env["GITHUB_RUN_ID"],
                                        run_attempt=self.env["GITHUB_RUN_ATTEMPT"],
                                        head_sha=self.env["GITHUB_SHA"],
                                        trusted_runtime_ref=self.env["KDD_TRUSTED_RUNTIME_REF"],
                                        platform=sys.platform, state=state))
        if state != "partial":
            self.assertEqual(report["modules"], [])
        return report

    def test_absent_marker_does_not_infer_a_project(self):
        directory = self.private / "kdd-suite-unmarked"
        directory.mkdir()
        worker.write_plan(directory / "plan-0.json", self.project / "tests", "test_unmarked")
        self.collect("not_found")

    def test_marker_refuses_existing_file_and_outside_projects(self):
        external = self.area / "outside"
        external.mkdir()
        self.assertNotEqual(self.mark(external).returncode, 0)
        self.assertFalse(self.marker.exists())
        self.require_marker()
        recorded = self.marker.read_bytes()
        self.assertNotEqual(self.mark().returncode, 0)
        self.assertEqual(self.marker.read_bytes(), recorded)

    def test_marker_from_other_attempt_or_sha_cannot_supply_evidence(self):
        self.require_marker()
        for key, different in (("GITHUB_RUN_ATTEMPT", "4"), ("GITHUB_SHA", "c"*40)):
            with self.subTest(key=key):
                original = self.env[key]
                self.env[key] = different
                self.collect("inconclusive")
                self.output.unlink()
                self.env[key] = original

    def test_collect_does_not_overwrite_existing_destination(self):
        data = b"Keep an unrelated existing artifact."
        self.output.write_bytes(data)
        result = self.run_python([str(worker.COLLECTOR), "--ci-output"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), data)

    def test_excess_plans_cannot_expand_public_report(self):
        self.require_marker()
        directory = self.private / "kdd-suite-unbounded"
        directory.mkdir()
        for index in range(513):
            worker.write_plan(directory / f"plan-{index}.json", self.project / "tests",
                              f"test_fixture_{index:03}")
        self.collect("inconclusive")

    def test_hosted_summary_survives_a_real_post_init_interruption(self):
        scripts = self.project / "scripts"
        scripts.mkdir()
        for name in worker.SCRIPTS:
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
        tests = self.project / "tests"
        for index in range(2):
            delay = 0 if index == 0 else 50
            failure = ("    def test_failure(self):\n"
                       "        self.fail('TRANSCRIPT_MUST_NOT_BE_PUBLISHED')\n")
            (tests / f"test_fixture_{index:02}.py").write_text(
                "import os,time,unittest\nfrom pathlib import Path\n"
                "class Probe(unittest.TestCase):\n"
                "    def test_control(self):\n"
                "        Path(__file__).with_suffix('.pid').write_text(str(os.getpid()))\n"
                f"        time.sleep({delay})\n" + (failure if index == 0 else ""), encoding="utf-8")
        self.require_marker()
        final = self.area / "full-report.json"
        worker.TimeoutObservation.interrupt_workers(self, scripts, tests, final)
        self.assertFalse(final.exists())
        report = self.collect("partial")
        self.assertEqual({row["name"]: row["phase"] for row in report["modules"]},
                         {"test_fixture_00": "completed", "test_fixture_01": "incomplete"})
        for row in report["modules"]:
            self.assertEqual(set(row), {"index", "name", "cases", "phase", "duration_seconds"})
        encoded = self.output.read_text(encoding="utf-8")
        self.assertNotIn("TRANSCRIPT_MUST_NOT_BE_PUBLISHED", encoded)
        self.assertNotIn("test_fixture_00.Probe", encoded)
        self.assertNotIn(str(self.project).replace("\\", "\\\\"), encoded)


class ProgressWorkflow(unittest.TestCase):
    def setUp(self):
        contents = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        self.steps = yaml.safe_load(contents)["jobs"]["validate"]["steps"]

    def step(self, key, value):
        matches = [step for step in self.steps if step.get(key) == value]
        self.assertEqual(len(matches), 1, value)
        return matches[0]

    def require_main_windows(self, condition):
        for boundary in ("matrix.os == 'windows-latest'", "github.event_name == 'push'",
                         "github.ref == 'refs/heads/main'", "github.repository == 'MauricioPerera/KDD'",
                         "!inputs.reusable_execution"):
            self.assertIn(boundary, condition)

    def test_only_native_windows_main_commands_activate_the_marker(self):
        command = self.step("name", "Run each contract's test_command")
        condition = command.get("env", {}).get("KDD_OBSERVE_POSTINIT", "")
        self.require_main_windows(condition)
        self.assertIn("'1'", condition)
        self.assertIn("--timeout 600", command["run"])
        self.assertNotIn("continue-on-error", command)


    def test_output_distinguishes_real_timeout_from_other_results(self):
        fixture = command_timing.CommandTiming()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        github_output = fixture.area / "step-outputs"
        fixture.environment["GITHUB_OUTPUT"] = str(github_output)
        ordinary_pass = fixture.report()
        ordinary_fail = fixture.report(failed=True)
        oracle = fixture.root / "tests/test_init_project.py"
        contract = fixture.contracts / "init-project.md"
        original = oracle.read_bytes()
        slow = original.replace(b"time.sleep(0.02)", b"time.sleep(40)")
        self.assertNotEqual(slow, original)
        oracle.write_bytes(slow)
        contract.write_bytes(contract.read_bytes().replace(
            hashlib.sha256(original).hexdigest().encode(),
            hashlib.sha256(slow).hexdigest().encode()))
        results = command_timing.run_all(str(fixture.contracts), str(fixture.root), timeout=3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["error"], "timeout")
        timeout = dict(ordinary_pass, ok=False, results=results)
        for command_result, expected in ((ordinary_pass, "false"), (ordinary_fail, "false"),
                                         (timeout, "true")):
            with self.subTest(expected=expected, ok=command_result["ok"]):
                fixture.write_report(command_result)
                github_output.write_text("", encoding="utf-8")
                process = fixture.summarize()
                metric = fixture.metric(process)
                self.assertEqual(metric["ok"], command_result["results"][0]["ok"])
                self.assertEqual(metric["error"], command_result["results"][0]["error"])
                self.assertEqual(github_output.read_text(encoding="utf-8").splitlines(),
                                 ["init_timed_out=" + expected])

    def test_artifact_is_conditioned_on_this_failure_and_bounded_output(self):
        timing = self.step("name", "Report init command duration")
        self.assertEqual(timing.get("id"), "init-command-timing")
        observe = self.step("id", "postinit-observation")
        upload = self.step("name", "Upload Windows post-init progress")
        self.require_main_windows(observe["if"])
        self.assertIn("always()", observe["if"])
        self.assertIn("steps.init-command-timing.outputs.init_timed_out == 'true'", observe["if"])
        self.assertEqual(observe["run"].strip(),
                         "python -I scripts/postinit_timeout_observation.py --ci-output")
        self.assertIn("always()", upload["if"])
        self.assertIn("steps.postinit-observation.outcome == 'success'", upload["if"])
        self.assertEqual(upload["with"]["path"], "${{ runner.temp }}/kdd-postinit-progress.json")
        self.assertEqual(upload["with"]["name"],
                         "kdd-postinit-progress-${{ github.run_id }}-${{ github.run_attempt }}-windows-latest")
        self.assertLess(self.steps.index(timing), self.steps.index(observe))
        self.assertLess(self.steps.index(observe), self.steps.index(upload))
        self.assertLess(self.steps.index(upload), self.steps.index(self.step("name", "Run unit tests (1/2)")))
        self.assertNotIn("continue-on-error", observe)
