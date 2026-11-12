"""Native post-init diagnostics that preserve the real timeout verdict."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.process_tree import run
from tests.test_fixture_preparation import directory_alias


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts/postinit_timeout_observation.py"
SCRIPTS = ("init_post_apply_suite.py", "run_test_suite.py", "process_tree.py")


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def evidence_snapshot(directory):
    paths = sorted(directory.glob("*.json"))
    return {path.name: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in paths}


def write_plan(plan, source, module, methods=("test_control",)):
    identities = [module + ".Probe." + method for method in methods]
    inventory = [{"id": identity, "origin": module, "module": module,
                  "class_name": module + ".Probe", "import_skip": False}
                 for identity in identities]
    write_json(plan, {"ids": identities, "start_dir": str(source), "pattern": "test_*.py",
                      "origin": module, "inventory": inventory})


class TimeoutObservation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kdd-partial-timeout-test-")
        self.addCleanup(temporary.cleanup)
        self.area = Path(temporary.name)
        self.private = self.area / "private"
        self.private.mkdir()
        self.project = Path(tempfile.mkdtemp(dir=self.private))

    def collect(self, state):
        result = subprocess.run([sys.executable, "-I", str(COLLECTOR), "--temp-root",
                                 str(self.private), "--project-root", str(self.project)],
                                capture_output=True, text=True,
                                encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(set(report), {"state", "modules"})
        self.assertEqual(report["state"], state, result.stdout)
        if state != "partial":
            self.assertEqual(report["modules"], [])
        return report["modules"]

    def plan(self, name, project=None):
        directory = self.private / name
        directory.mkdir()
        source = (self.project if project is None else project) / "tests"
        source.mkdir(parents=True, exist_ok=True)
        plan = directory / "plan-0.json"
        write_plan(plan, source, "test_fixture")
        return plan

    def interrupt_workers(self, scripts, tests, final):
        env = dict(os.environ, TEMP=str(self.private), TMP=str(self.private), TMPDIR=str(self.private))
        if os.name == "nt":
            command = [sys.executable, str(scripts / "init_post_apply_suite.py"),
                       "--repo-root", str(self.project), "--report-json", str(final)]
            with self.assertRaises(subprocess.TimeoutExpired):
                run(command, cwd=self.project, env=env, capture_output=True, timeout=9)
            return
        # POSIX child workers can create new sessions. Contain the native
        # workers directly in this fixture and verify the timed-out PID exited.
        directory = self.private / "kdd-suite-native"
        directory.mkdir()
        commands = []
        for index in (0, 1):
            plan = directory / f"plan-{index}.json"
            result = directory / f"result-{index}.json"
            methods = ("test_control", "test_failure") if index == 0 else ("test_control",)
            write_plan(plan, tests, f"test_fixture_{index:02}", methods)
            commands.append([sys.executable, "-I", str(scripts / "run_test_suite.py"),
                             "--worker-plan", str(plan), "--worker-report", str(result)])
        completed = run(commands[0], cwd=self.project, env=env, capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        with self.assertRaises(subprocess.TimeoutExpired):
            run(commands[1], cwd=self.project, env=env, capture_output=True, timeout=4)
        pid = int((tests / "test_fixture_01.pid").read_text(encoding="utf-8"))
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_real_timeout_leaves_one_completed_module_and_incomplete_workers(self):
        source = self.project
        scripts = source / "scripts"
        tests = source / "tests"
        scripts.mkdir(parents=True)
        tests.mkdir()
        for name in SCRIPTS:
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
        for index in range(12):
            delay = 0 if index == 0 else 45
            failure = "    def test_failure(self):\n        self.fail('completed with a test failure')\n"
            (tests / f"test_fixture_{index:02}.py").write_text(
                "import os\nfrom pathlib import Path\nimport time\nimport unittest\n"
                "class Probe(unittest.TestCase):\n"
                "    def test_control(self):\n"
                "        Path(__file__).with_suffix('.pid').write_text(str(os.getpid()))\n"
                f"        time.sleep({delay})\n"
                "        self.assertTrue(True)\n" + (failure if index == 0 else ""), encoding="utf-8")
        final = self.area / "postinit.json"
        self.interrupt_workers(scripts, tests, final)
        self.assertFalse(final.exists())
        directory, = (path for path in self.private.glob("kdd-suite-*")
                      if any(path.glob("plan-*.json")))
        artifacts = evidence_snapshot(directory)
        plans = {int(path.stem.split("-")[1]): json.loads(path.read_bytes())
                 for path in directory.glob("plan-*.json")}
        self.assertLess(len(plans), 12)
        self.assertGreater(len(plans), 1)
        results = {int(path.stem.split("-")[1]): json.loads(path.read_bytes())
                   for path in directory.glob("result-*.json")}
        self.assertEqual([plans[index]["origin"] for index in sorted(results)], ["test_fixture_00"])
        completed, = results.values()
        self.assertFalse(completed["ok"])
        self.assertEqual(completed["tests_run"], 2)
        self.assertEqual(len(completed["failures"]), 1)

        modules = self.collect("partial")
        self.assertEqual([module["index"] for module in modules], sorted(plans))
        for module in modules:
            index = module["index"]
            self.assertEqual(set(module), {"index", "name", "phase", "cases", "duration_seconds"})
            self.assertEqual(module["name"], plans[index]["origin"])
            self.assertEqual(module["cases"], len(plans[index]["ids"]))
            if index in results:
                self.assertEqual(module["phase"], "completed")
                elapsed = (artifacts[f"result-{index}.json"][1] - artifacts[f"plan-{index}.json"][1]) / 1e9
                self.assertAlmostEqual(module["duration_seconds"], elapsed, delta=0.001)
            else:
                self.assertEqual(module["phase"], "incomplete")
                self.assertIsNone(module["duration_seconds"])
        self.assertEqual(evidence_snapshot(directory), artifacts)
        self.assertFalse(final.exists())
        result_path = directory / f"result-{next(iter(results))}.json"
        result_path.write_text(result_path.read_text(encoding="utf-8").replace(
            "test_fixture_00", "test_foreign"), encoding="utf-8")
        self.collect("inconclusive")

    def test_foreign_suite_is_not_mistaken_for_postinit_evidence(self):
        (self.project / "tests").mkdir()
        plan = self.plan("kdd-suite-foreign", self.private / "kdd init profile unrelated")
        before = plan.read_bytes()
        self.collect("not_found")
        self.assertEqual(plan.read_bytes(), before)

    def test_ambiguous_suites_are_not_combined(self):
        self.plan("kdd-suite-first")
        self.collect("partial")
        self.plan("kdd-suite-second")
        self.collect("inconclusive")

    def test_rejects_a_hardlinked_plan_and_preserves_its_external_target(self):
        plan = self.plan("kdd-suite-linked")
        self.collect("partial")
        target = self.area / "external.json"
        plan.rename(target)
        expected = target.read_bytes()
        os.link(target, plan)
        self.collect("inconclusive")
        self.assertEqual(target.read_bytes(), expected)
        self.assertEqual(plan.read_bytes(), expected)

    def test_truncated_result_cannot_be_reported_as_completed(self):
        plan = self.plan("kdd-suite-incomplete")
        self.collect("partial")
        result = plan.with_name("result-0.json")
        result.write_text('{"expected_ids": [', encoding="utf-8")
        self.collect("inconclusive")
        self.assertEqual(result.read_text(encoding="utf-8"), '{"expected_ids": [')

    def test_rejects_a_plan_above_the_byte_limit(self):
        plan = self.plan("kdd-suite-oversized")
        self.collect("partial")
        raw = plan.read_bytes()
        limit = 256 * 1024
        plan.write_bytes(raw + b" " * (limit - len(raw)))
        self.collect("partial")
        with plan.open("ab") as stream:
            stream.write(b" ")
        self.collect("inconclusive")

    def test_rejects_a_duplicate_module_with_two_plan_indices(self):
        plan = self.plan("kdd-suite-duplicate")
        self.collect("partial")
        shutil.copyfile(plan, plan.with_name("plan-1.json"))
        self.collect("inconclusive")

    def test_does_not_follow_a_suite_directory_alias_outside_the_private_root(self):
        plan = self.plan("kdd-suite-aliased")
        self.collect("partial")
        outside = self.area / "outside"
        plan.parent.rename(outside)
        before = evidence_snapshot(outside)
        directory_alias(plan.parent, outside, self.area)
        self.collect("inconclusive")
        self.assertEqual(evidence_snapshot(outside), before)


if __name__ == "__main__":
    unittest.main()
