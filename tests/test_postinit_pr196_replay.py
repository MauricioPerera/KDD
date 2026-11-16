"""Integration controls for a full init-command replay and its evidence."""
import hashlib
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

from scripts.trusted_ci import MANAGED_RUNTIME_FILES, RUNTIME_FILES
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
                        GITHUB_RUN_ID="19601", GITHUB_RUN_ATTEMPT="2")
        git(self.source, "init", "-q", "-b", "main")
        configure_git(self.source, {"user.name": "Replay fixture", "user.email": "replay@example.invalid"},
                      ephemeral=True)
        for name in (*RUNTIME_FILES, *MANAGED_RUNTIME_FILES):
            shutil.copyfile(ROOT / "scripts" / name, self.source / "scripts" / name)
        self.runtime, _ = self.commit_fixture()
        self.env["KDD_TRUSTED_RUNTIME_REF"] = self.runtime

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
        shutil.copyfile(self.source / "scripts/trusted_ci.py", stage)
        bundle = self.area / "bundle"
        subprocess.run([sys.executable, "-I", str(stage), "prepare", "--repo-root", str(self.source),
                        "--trusted-ref", self.runtime, "--bundle-dir", str(bundle)],
                       check=True, capture_output=True, timeout=40)
        return bundle

    def run_cli(self, sha, tree, bundle):
        # Only replace the three exact reviewed identities at the boundary.
        script = (
            "import runpy,sys;"
            "namespace=runpy.run_path(sys.argv[1]);"
            "assert 'main' in namespace, 'replay CLI is pending';"
            "main=namespace['main'];"
            "main.__globals__.update(SOURCE_SHA=sys.argv[2], SOURCE_TREE=sys.argv[3], "
            "RUNTIME_SHA=sys.argv[4]);"
            "raise SystemExit(main(['--source',sys.argv[5],'--bundle',sys.argv[6]]))"
        )
        return subprocess.run([sys.executable, "-I", "-c", script, str(REPLAY), sha, tree, self.runtime,
                               str(self.source), str(bundle)],
                              env=self.env, capture_output=True, text=True, encoding="utf-8", timeout=35)

    def profile_fixture(self, cases):
        marker = self.area / "bootstrap-witness"
        profile = dict(kind="summary", platform="win32", workers=10, tests_run=cases,
                       expected_count=cases, fixture_omitted_count=0, skipped=106,
                       duration_seconds=0.01, modules=227)
        self.oracle.write_text(
            "import unittest\nfrom pathlib import Path\nclass Bootstrap(unittest.TestCase):\n"
            " def test_run(self):\n"
            f"  Path({str(marker)!r}).open('a').write('1')\n"
            f"  print({('KDD_POST_INIT_PROFILE ' + json.dumps(profile))!r})\n",
            encoding="utf-8",
        )
        return marker

    def test_cli_writes_verified_success_and_refuses_reusing_its_receipt(self):
        witness = self.profile_fixture(2374)
        sha, tree = self.commit_fixture()
        bundle = self.make_bundle()
        wrong = self.run_cli(PROBE, tree, bundle)
        self.assertEqual(wrong.returncode, 2, wrong.stderr)
        self.assertFalse(witness.exists())
        self.assertFalse((self.runner / "kdd-postinit-pr196-replay.json").exists())
        proc = self.run_cli(sha, tree, bundle)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = self.runner / "kdd-postinit-pr196-replay.json"
        raw = output.read_bytes()
        result = json.loads(raw)
        self.assertEqual(result["outcome"], dict(ok=True, error=None, exit_code=0))
        self.assertEqual(result["profile"], {"cases": 2374, "workers": 10})
        self.assertIsNone(result["observation"])
        self.assertEqual((result["source_sha"], result["probe_sha"]), (sha, PROBE))
        self.assertEqual(witness.read_text(), "1")
        self.assertNotEqual(self.run_cli(sha, tree, bundle).returncode, 0)
        self.assertEqual(output.read_bytes(), raw)
        self.assertEqual(witness.read_text(), "1")

    def test_cli_rejects_wrong_success_profile_and_preserves_raw_outcome(self):
        self.profile_fixture(2373)
        sha, tree = self.commit_fixture()
        proc = self.run_cli(sha, tree, self.make_bundle())
        self.assertEqual(proc.returncode, 2, proc.stderr)
        result = json.loads((self.runner / "kdd-postinit-pr196-replay.json").read_bytes())
        self.assertEqual(result["outcome"], dict(ok=True, error=None, exit_code=0))
        self.assertIsNone(result["profile"])

    def test_cli_rejects_an_internally_consistent_tampered_bundle_before_import(self):
        self.profile_fixture(2374)
        sha, tree = self.commit_fixture()
        bundle = self.make_bundle()
        witness = self.area / "untrusted-module-executed"
        target = bundle / "validate_test_commands.py"
        content = target.read_bytes() + f"\nfrom pathlib import Path\nPath({str(witness)!r}).touch()\n".encode()
        target.write_bytes(content)
        manifest = bundle / "manifest.json"
        declared = json.loads(manifest.read_bytes())
        declared["files"][target.name] = hashlib.sha256(content).hexdigest()
        manifest.write_text(json.dumps(declared), encoding="utf-8")
        process = self.run_cli(sha, tree, bundle)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertIn("runtime", process.stderr.lower())
        self.assertFalse(witness.exists())
        self.assertFalse((self.runner / "kdd-postinit-pr196-replay.json").exists())

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
        self.assertEqual((report["run_id"], report["run_attempt"], report["runtime_sha"]), ("19601", "2", self.runtime))
        observed = report["observation"]
        self.assertEqual(observed["head_sha"], sha)
        self.assertEqual(observed["state"], "partial")
        self.assertGreaterEqual(report["handoff_seconds"], 0)
        self.assertLess(report["handoff_seconds"], report["duration_seconds"])
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
        self.assertIsNone(report["handoff_seconds"])

    def test_corrupt_collector_output_still_preserves_real_timeout(self):
        self.oracle.write_text(
            "import time,unittest\nclass Bootstrap(unittest.TestCase):\n def test_run(self):\n"
            "  time.sleep(90)\n", encoding="utf-8")
        self.collector.write_text(
            "import os\nfrom pathlib import Path\n"
            "(Path(os.environ['RUNNER_TEMP'])/'kdd-postinit-progress.json').write_text('invalid JSON')\n",
            encoding="utf-8")
        self.commit_fixture()
        code, report = self.use(probe.replay, self.source, self.make_bundle(), self.env, timeout=5)
        self.assertEqual(code, 124)
        self.assertEqual(report["outcome"], dict(ok=False, error="timeout", exit_code=None))
        self.assertEqual(report["observation"]["state"], "inconclusive")
        self.assertEqual(report["observation"]["modules"], [])
        self.assertIsNone(report["handoff_seconds"])


class ReplayWorkflow(unittest.TestCase):
    def test_workflow_pins_replay_to_read_only_isolated_branch(self):
        path = ROOT / ".github/workflows/postinit-pr196-replay.yml"
        self.assertTrue(path.is_file())
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(workflow[True], dict(push={"branches": ["codex/postinit-pr196-replay"]}))
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job, = workflow["jobs"].values()
        self.assertEqual(job["runs-on"], "windows-latest")
        self.assertEqual(job["if"], "github.repository == 'MauricioPerera/KDD'")
        checkouts = [step["with"] for step in job["steps"] if step.get("uses","").startswith("actions/checkout@")]
        control, measured = checkouts
        self.assertFalse(control["persist-credentials"])
        self.assertFalse(measured["persist-credentials"])
        self.assertEqual(measured["ref"], SOURCE)
        self.assertNotEqual(control["path"], measured["path"])
        self.assertEqual(job["defaults"]["run"]["working-directory"], measured["path"])
        self.assertEqual(job["env"]["KDD_TRUSTED_RUNTIME_REF"], RUNTIME)
        names = [step.get("name") for step in job["steps"]]
        operation = "Replay complete init command and collect after timeout"
        target = job["steps"][names.index(operation)]
        self.assertEqual(target["shell"], "bash")
        self.assertEqual(target["run"].strip(), "python -I ../control/.github/diagnostics/"
                         "postinit_pr196_replay.py --source . --bundle " + '"$KDD_TRUSTED_BUNDLE"')
        for setup in ("Select native Git on Windows", "Materialize reviewed isolated CI runtime",
                      "Install pinned context compatibility dependencies", "Install pinned workflow checker",
                      "Install measured Board dependencies", "Install measured Pages dependencies",
                      "Prepare pinned MCP SDK environment", "Run required MCP SDK protocol smoke",
                      "Prepare native Windows test temp", "Build and validate Pages for PR"):
            self.assertLess(names.index(setup), names.index(operation))
        uploads = [step for step in job["steps"] if step.get("uses","").startswith("actions/upload-artifact@")]
        upload, = uploads
        self.assertEqual(upload["if"], "${{ always() }}")
        self.assertEqual(upload["uses"], "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9")
        self.assertEqual(upload["with"]["path"], "${{ runner.temp }}/kdd-postinit-pr196-replay.json")
        self.assertEqual(upload["with"]["if-no-files-found"], "error")
        for step in job["steps"]:
            self.assertNotIn("continue-on-error", step)
