"""Exercise the official timeout handoff without modifying its verdict."""
import hashlib
from inspect import unwrap
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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
        raw = self.output.read_bytes()
        self.assertLessEqual(len(raw), 192 * 1024)
        report = json.loads(raw)
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

    def observed_plan(self, name="test_ci_observed"):
        directory = self.private / "kdd-suite-observed"
        directory.mkdir(exist_ok=True)
        destination = directory / "plan-0.json"
        worker.write_plan(destination, self.project / "tests", name)
        return destination

    def test_stale_run_attempt_or_sha_cannot_supply_otherwise_valid_evidence(self):
        self.require_marker()
        self.observed_plan()
        declared = self.collect("partial")
        self.assertEqual([entry["name"] for entry in declared["modules"]], ["test_ci_observed"])
        self.output.unlink()
        for key, different in (("GITHUB_RUN_ID", "4322"), ("GITHUB_RUN_ATTEMPT", "4"),
                               ("GITHUB_SHA", "c"*40)):
            with self.subTest(key=key), patch.dict(self.env, {key: different}):
                self.collect("inconclusive")
                self.output.unlink()

    def test_marker_hardlink_cannot_redirect_the_collector(self):
        self.require_marker()
        self.observed_plan()
        external = self.area / "marker-canary.json"
        self.marker.rename(external)
        expected = external.read_bytes()
        os.link(external, self.marker)
        self.collect("inconclusive")
        self.assertEqual(external.read_bytes(), expected)

    def test_project_junction_cannot_redirect_to_an_external_directory(self):
        self.require_marker()
        self.observed_plan()
        outside = self.area / "outside"
        self.project.rename(outside)
        canary = outside / "canary.txt"
        canary.write_bytes(b"external")
        worker.directory_alias(self.project, outside, self.area)
        self.collect("inconclusive")
        self.assertEqual(canary.read_bytes(), b"external")

    def test_unsafe_module_name_is_rejected_before_publication(self):
        self.require_marker()
        for name in ("../outside", "test_" + "x"*156):
            with self.subTest(length=len(name)):
                self.observed_plan(name)
                self.collect("inconclusive")
                self.output.unlink()

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
        for index in range(512):
            worker.write_plan(directory / f"plan-{index}.json", self.project / "tests",
                              "test_" + "x"*151 + f"{index:04}")
        report = self.collect("partial")
        self.assertEqual(len(report["modules"]), 512)
        self.assertTrue(all(len(row["name"]) == 160 for row in report["modules"]))
        self.output.unlink()
        worker.write_plan(directory / "plan-512.json", self.project / "tests", "test_over_capacity")
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
        self.assertTrue((tests / "test_fixture_01.pid").is_file(), "The slow worker did not start")
        report = self.collect("partial")
        self.assertEqual({row["name"]: row["phase"] for row in report["modules"]},
                         {"test_fixture_00": "completed", "test_fixture_01": "incomplete"})
        for row in report["modules"]:
            self.assertEqual(set(row), {"index", "name", "cases", "phase", "duration_seconds"})
        encoded = self.output.read_text(encoding="utf-8")
        self.assertNotIn("TRANSCRIPT_MUST_NOT_BE_PUBLISHED", encoded)
        self.assertNotIn("test_fixture_00.Probe", encoded)
        self.assertNotIn(str(self.project).replace("\\", "\\\\"), encoded)


    def test_real_init_fixture_marks_the_exact_copy_before_spawning_post_init(self):
        if not (ROOT / "tests/test_init_project.py").is_file():
            self.skipTest("Bootstrap removes its outer integration oracle from the initialized copy")
        from tests import test_init_project as bootstrap

        scripts = self.project / "scripts"
        scripts.mkdir()
        for name in worker.SCRIPTS:
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
        for name in ("validate_contracts.py", "validate_okf.py", "validate_specs.py",
                     "validate_changelog.py", "validate_completion.py"):
            (scripts / name).write_text('print("Summary: PASS=0 FAIL=0 SKIP=0")\n', encoding="utf-8")
        tests = self.project / "tests"
        (tests / "test_fixture.py").write_text(
            "import unittest\nclass Probe(unittest.TestCase):\n"
            "    def test_completed(self):\n        self.assertTrue(True)\n", encoding="utf-8")
        fixture = bootstrap.TestInitProject()
        fixture.repo = str(self.project)
        original_run = bootstrap._run
        body = unwrap(bootstrap.TestInitProject.test_gates_verdes_post_apply_en_copia)

        for occupied in (False, True):
            with self.subTest(marker_exists=occupied):
                if self.marker.exists():
                    self.marker.unlink()
                sentinel = b"Do not overwrite a pre-existing diagnostic."
                if occupied:
                    self.marker.write_bytes(sentinel)
                (tests / "test_init_project.py").write_text("# outer recursion guard\n", encoding="utf-8")
                launched = []

                def call(arguments, cwd):
                    if arguments[0] == "scripts/init_post_apply_suite.py":
                        self.assertTrue(self.marker.is_file(), "Marker must exist before worker launch")
                        if occupied:
                            self.assertEqual(self.marker.read_bytes(), sentinel)
                        else:
                            record = json.loads(self.marker.read_bytes())
                            self.assertEqual(record["project"], self.project.name)
                        self.assertEqual(Path(cwd).resolve(), self.project)
                        launched.append(arguments[0])
                    return original_run(arguments, cwd)

                with (
                    patch.dict(os.environ, dict(self.env, KDD_OBSERVE_POSTINIT="1")),
                    patch.object(tempfile, "tempdir", str(self.private)),
                    patch.object(bootstrap, "_copy_repo"),
                    patch.object(bootstrap, "_run_cli", return_value=subprocess.CompletedProcess([], 0)),
                    patch.object(bootstrap, "_run", side_effect=call),
                ):
                    try:
                        body(fixture)
                    except ImportError as error:
                        self.fail(str(error))
                self.assertEqual(launched, ["scripts/init_post_apply_suite.py"])


class ProgressWorkflow(unittest.TestCase):
    def setUp(self):
        contents = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        self.job = yaml.safe_load(contents)["jobs"]["validate"]
        self.steps = self.job["steps"]

    def step(self, key, value):
        matches = [step for step in self.steps if step.get(key) == value]
        self.assertEqual(len(matches), 1, value)
        return matches[0]

    WINDOWS_MAIN = ("github.repository == 'MauricioPerera/KDD' && "
                    "matrix.os == 'windows-latest' && !inputs.reusable_execution && "
                    "github.event_name == 'push' && github.ref == 'refs/heads/main' && "
                    "github.workflow_ref == 'MauricioPerera/KDD/.github/workflows/validate.yml@refs/heads/main'")

    def test_only_native_windows_main_commands_activate_the_marker(self):
        command = self.step("name", "Run each contract's test_command")
        condition = command.get("env", {}).get("KDD_OBSERVE_POSTINIT", "")
        self.assertEqual(" ".join(condition.split()), "${{ " + self.WINDOWS_MAIN + " && '1' || '' }}")
        self.assertEqual(command["run"], (
            'python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" commands --repo-root . '
            '--contracts-dir "$KDD_CONTRACTS_DIR" --timeout 600 --deduplicate '
            '--workers "$KDD_CONTRACT_WORKERS" --report-dir "$RUNNER_TEMP/kdd-command-reports" '
            '--exclusive-commands-json "$KDD_EXCLUSIVE_CONTRACT_COMMANDS"'
        ))
        self.assertNotIn("continue-on-error", command)

    def test_both_suites_keep_matrix_and_first_pass_coverage(self):
        self.assertEqual(self.job["strategy"]["matrix"]["os"], ["ubuntu-latest", "windows-latest"])
        first = self.step("name", "Run unit tests (1/2)")
        second = self.step("name", "Run unit tests (2/2)")
        for step in first, second:
            self.assertNotIn("if", step)
            self.assertNotIn("continue-on-error", step)
            self.assertEqual(step["env"]["KDD_SKIP_INIT_POST_APPLY_SUITE"], "1")
        self.assertEqual(first["run"], second["run"])
        self.assertEqual(first["env"]["COVERAGE_PROCESS_START"],
                         "${{ (!inputs.reusable_execution && github.repository == 'MauricioPerera/KDD') && format('{0}/kdd-python-coverage-{1}-{2}/coverage.ini', runner.temp, github.run_id, github.run_attempt) || '' }}")
        self.assertNotIn("COVERAGE_PROCESS_START", second["env"])

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
        other = dict(results[0], path=str(fixture.contracts / "another-contract.md"))
        unrelated_timeout = dict(ordinary_pass, ok=False, results=ordinary_pass["results"] + [other])
        for command_result, expected in ((ordinary_pass, "false"), (ordinary_fail, "false"),
                                         (timeout, "true"), (unrelated_timeout, "false")):
            with self.subTest(expected=expected, outcomes=len(command_result["results"])):
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
        self.assertEqual(" ".join(observe["if"].split()), "${{ always() && " + self.WINDOWS_MAIN
                         + " && steps.init-command-timing.outputs.init_timed_out == 'true' }}")
        self.assertEqual(observe["run"].strip(),
                         "python -I scripts/postinit_timeout_observation.py --ci-output")
        self.assertEqual(" ".join(upload["if"].split()),
                         "${{ always() && steps.postinit-observation.outcome == 'success' }}")
        self.assertEqual(upload["uses"], "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9")
        self.assertEqual(upload["with"]["if-no-files-found"], "error")
        self.assertIn(upload["with"].get("overwrite"), (None, False))
        self.assertEqual(upload["with"]["path"], "${{ runner.temp }}/kdd-postinit-progress.json")
        self.assertEqual(upload["with"]["name"],
                         "kdd-postinit-progress-${{ github.run_id }}-${{ github.run_attempt }}-windows-latest")
        self.assertLess(self.steps.index(timing), self.steps.index(observe))
        self.assertLess(self.steps.index(observe), self.steps.index(upload))
        self.assertLess(self.steps.index(upload), self.steps.index(self.step("name", "Run unit tests (1/2)")))
        self.assertNotIn("continue-on-error", observe)
