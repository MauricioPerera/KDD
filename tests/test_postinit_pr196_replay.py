"""Integration controls for a full init-command replay and its evidence."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.test_fixture_preparation import configure_git
from tests.test_postinit_timeout_observation import write_plan

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / ".github/diagnostics/postinit_pr196_replay.py"
SPEC = importlib.util.spec_from_file_location("postinit_pr196_replay", REPLAY)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
RUNTIME = "74d357f7099651b9b39dc8088f725183a672ec94"
SOURCE = "088225c2ff241b773353825f45c9e63a57861173"
PROBE = "f" * 40
INIT = "python -m unittest tests/test_init_project.py"


def git(root, *args):
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(root), *args],
                                   encoding="utf-8", stderr=subprocess.PIPE, timeout=30).strip()


class RealReplay(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="kdd-pr196-oracle-")
        self.addCleanup(temp.cleanup)
        self.area = Path(temp.name).resolve()
        self.source = self.area / "source"
        (self.source / "tests").mkdir(parents=True)
        (self.source / "scripts").mkdir()
        (self.source / "tests/__init__.py").touch()
        self.collector = self.source / "scripts/postinit_timeout_observation.py"
        shutil.copyfile(ROOT / "scripts/postinit_timeout_observation.py", self.collector)
        self.oracle = self.source / "tests/test_init_project.py"
        self.runner = self.area / "runner"
        self.private = self.runner / "kdd-native-tests-probe"
        self.private.mkdir(parents=True)
        self.env = dict(os.environ, RUNNER_TEMP=str(self.runner), TEMP=str(self.private),
                        TMP=str(self.private), TMPDIR=str(self.private),
                        GITHUB_WORKSPACE=str(self.source), GITHUB_SHA=PROBE,
                        GITHUB_RUN_ID="19601", GITHUB_RUN_ATTEMPT="2",
                        KDD_TRUSTED_RUNTIME_REF=RUNTIME)
        git(self.source, "init", "-q", "-b", "main")
        configure_git(self.source, {"user.name": "Replay fixture", "user.email": "replay@example.invalid"},
                      ephemeral=True)

    def commit_fixture(self):
        git(self.source, "add", "-A")
        git(self.source, "commit", "-qm", "Replay fixture")
        return git(self.source, "rev-parse", "HEAD"), git(self.source, "rev-parse", "HEAD^{tree}")

    def use(self, method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except NotImplementedError as exc:
            self.fail(str(exc))

    def make_bundle(self):
        stage = self.area / "trusted_ci.py"
        content = subprocess.check_output(["git", "--no-replace-objects", "-C", str(ROOT),
                                           "show", RUNTIME + ":scripts/trusted_ci.py"], timeout=30)
        stage.write_bytes(content)
        bundle = self.area / "bundle"
        subprocess.run([sys.executable, "-I", str(stage), "prepare", "--repo-root", str(ROOT),
                        "--trusted-ref", RUNTIME, "--bundle-dir", str(bundle)],
                       check=True, capture_output=True, timeout=40)
        return bundle

    def test_real_git_checkout_checks_commit_tree_and_dirty_state(self):
        self.oracle.write_text("# Git fixture\n", encoding="utf-8")
        sha, tree = self.commit_fixture()
        self.use(probe.check_checkout, self.source, sha, tree)
        with self.assertRaises(ValueError):
            self.use(probe.check_checkout, self.source, PROBE, tree)
        with self.assertRaises(ValueError):
            self.use(probe.check_checkout, self.source, sha, PROBE)
        self.oracle.write_text("# changed after commit\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.use(probe.check_checkout, self.source, sha, tree)
        git(self.source, "restore", "--", str(self.oracle))
        (self.source / "untracked.py").touch()
        with self.assertRaises(ValueError):
            self.use(probe.check_checkout, self.source, sha, tree)

    def test_timeout_preserves_the_outer_verdict_and_collects_real_workers(self):
        project = self.private / "initialized"
        scripts = project / "scripts"
        tests = project / "tests"
        scripts.mkdir(parents=True)
        tests.mkdir()
        for name in ("run_test_suite.py", "process_tree.py"):
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
        job = self.private / "kdd-suite-real"
        job.mkdir()
        for index, (name, body) in enumerate((
                ("test_completed", "  self.assertTrue(True)\n"),
                ("test_pending", "  Path(__file__).with_suffix('.witness').touch()\n  time.sleep(90)\n"))):
            (tests / (name + ".py")).write_text(
                "from pathlib import Path\nimport time,unittest\n"
                "class Probe(unittest.TestCase):\n def test_control(self):\n" + body, encoding="utf-8")
            write_plan(job / f"plan-{index}.json", tests, name)
        self.oracle.write_text(
            "import os, subprocess, sys, unittest\nfrom pathlib import Path\n"
            "from scripts.postinit_timeout_observation import mark_project\n"
            "class Bootstrap(unittest.TestCase):\n"
            " def test_run(self):\n"
            f"  project=Path({str(project)!r})\n"
            f"  job=Path({str(job)!r})\n"
            "  self.assertEqual(os.environ['KDD_OBSERVE_POSTINIT'],'1')\n"
            "  self.assertTrue(mark_project(project))\n"
            "  for i in range(2):\n"
            "   subprocess.run([sys.executable,'-I',str(project/'scripts/run_test_suite.py'),"
            "'--worker-plan',str(job/f'plan-{i}.json'),'--worker-report',str(job/f'result-{i}.json')],check=True,cwd=project)\n",
            encoding="utf-8",
        )
        sha, tree = self.commit_fixture()
        exit_code, report = self.use(probe.replay, self.source, self.make_bundle(), self.env, timeout=12)
        self.assertEqual(exit_code, 124, report)
        self.assertEqual(report["outcome"], dict(ok=False, error="timeout", exit_code=None))
        self.assertTrue((tests / "test_pending.witness").is_file())
        self.assertEqual((report["source_sha"], report["source_tree"], report["probe_sha"]), (sha, tree, PROBE))
        self.assertEqual((report["run_id"], report["run_attempt"], report["runtime_sha"]), ("19601", "2", RUNTIME))
        observed = report["observation"]
        self.assertEqual(observed["head_sha"], sha)
        self.assertEqual(observed["state"], "partial")
        self.assertEqual({row["name"]:row["phase"] for row in observed["modules"]},
                         {"test_completed": "completed", "test_pending": "incomplete"})
        serialized = json.dumps(report)
        self.assertNotIn("test_completed.Probe", serialized)
        self.assertNotIn(str(project).replace("\\", "\\\\"), serialized)
        self.assertLessEqual(len(serialized.encode("utf-8")), 192 * 1024)
        self.assertEqual(self.env["GITHUB_SHA"], PROBE)

    def test_real_assertion_failure_preserves_code_without_timeout_observation(self):
        self.oracle.write_text(
            "import unittest\nclass Bootstrap(unittest.TestCase):\n def test_run(self):\n"
            "  self.fail('transcript must stay out of the artifact')\n", encoding="utf-8")
        self.commit_fixture()
        code, report = self.use(probe.replay, self.source, self.make_bundle(), self.env, timeout=15)
        self.assertEqual(code, 1)
        self.assertEqual(report["outcome"], dict(ok=False, error=None, exit_code=1))
        self.assertIsNone(report["observation"])
        self.assertNotIn("transcript", json.dumps(report))
        self.assertEqual(probe.replay.__defaults__, (600,))

    def test_timeout_before_the_fixture_marks_a_project_stays_a_timeout(self):
        self.oracle.write_text(
            "import time,unittest\nclass Bootstrap(unittest.TestCase):\n def test_run(self):\n"
            "  time.sleep(90)\n", encoding="utf-8")
        self.commit_fixture()
        code, report = self.use(probe.replay, self.source, self.make_bundle(), self.env, timeout=5)
        self.assertEqual(code, 124)
        self.assertEqual(report["outcome"], dict(ok=False, error="timeout", exit_code=None))
        self.assertEqual(report["observation"]["state"], "not_found")
        self.assertEqual(report["observation"]["modules"], [])


class ReplayWorkflow(unittest.TestCase):
    def test_workflow_pins_replay_to_read_only_isolated_branch(self):
        path = ROOT / ".github/workflows/postinit-pr196-replay.yml"
        self.assertTrue(path.is_file())
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(workflow[True], dict(push={"branches": ["codex/postinit-pr196-replay"]}))
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job, = workflow["jobs"].values()
        self.assertEqual(job["runs-on"], "windows-latest")
        self.assertIn("github.repository == 'MauricioPerera/KDD'", job["if"])
        checkouts = [step["with"] for step in job["steps"] if step.get("uses","").startswith("actions/checkout@")]
        control, measured = checkouts
        self.assertFalse(control["persist-credentials"])
        self.assertFalse(measured["persist-credentials"])
        self.assertEqual(measured["ref"], SOURCE)
        self.assertNotEqual(control["path"], measured["path"])
        uploads = [step for step in job["steps"] if step.get("uses","").startswith("actions/upload-artifact@")]
        upload, = uploads
        self.assertIn("always()", upload["if"])
        self.assertEqual(upload["uses"], "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9")
        self.assertEqual(upload["with"]["path"], "${{ runner.temp }}/kdd-postinit-pr196-replay.json")
        self.assertEqual(upload["with"]["if-no-files-found"], "error")
        for step in job["steps"]:
            self.assertNotIn("continue-on-error", step)
