"""Reject substitutions across the adoption transport and checkout boundaries."""

from copy import deepcopy
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml

from tests import adoption_remediation_support as support
from tests import test_adoption_trusted_pr as trusted
from tests import test_fixture_preparation as fixtures
from tests import test_plugin_odd_egm_review as review


ARCHIVE_ATTACK = """
def alter_archive(archive, variant):
    import io
    import tarfile
    with tarfile.open(archive, "r:") as snapshot:
        members = [(entry, snapshot.extractfile(entry).read() if entry.isfile() else None)
                   for entry in snapshot]
    revision = next(item for item in members if item[0].name == "revision.txt")
    if variant == "omit":
        members.remove(revision)
    elif variant == "duplicate":
        members.append(revision)
    elif variant == "blob":
        members[members.index(revision)] = (revision[0], b"x" * len(revision[1]))
    elif variant == "link":
        entry = tarfile.TarInfo("alias")
        entry.type = tarfile.SYMTYPE
        entry.linkname = "../../outside-marker"
        members.append((entry, None))
    elif variant == "escape":
        entry = tarfile.TarInfo("../../outside-marker")
        entry.size = 7
        members.append((entry, b"changed"))
    with tarfile.open(archive, "w") as snapshot:
        for entry, data in members:
            snapshot.addfile(entry, io.BytesIO(data) if data is not None else None)
"""


class AdversarialTransportTests(unittest.TestCase):
    def setUp(self):
        self.consumer = review.PluginOddEgmReviewTests()
        self.addCleanup(self.consumer.doCleanups)
        self.consumer.setUp()
        path = self.consumer.root / ".github/workflows/kdd-validate.yml"
        self.consumer.workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    def test_a02_managed_link_is_rejected_without_touching_the_target(self):
        consumer = self.consumer
        candidate = consumer.editorial_candidate()
        managed = consumer.root / ".kdd"
        outside = consumer.root.parent / "managed-outside"
        managed.rename(outside)
        original = {path.name: path.read_bytes() for path in outside.iterdir()}
        fixtures.directory_alias(managed, outside, consumer.root.parent)
        self.addCleanup(managed.rmdir if sys.platform == "win32" else managed.unlink)
        approved_launcher = consumer.root.parent / "validate.py"
        approved_launcher.write_bytes(original["validate.py"])
        process = consumer.invoke("entry", approved_launcher, (
            "review", "--repo-root", str(consumer.root), "--approved-ref", consumer.approved,
            "--base-ref", consumer.approved, "--candidate-ref", candidate,
        ))
        self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
        self.assertIn("Expected a regular local path: .kdd/", process.stderr)
        self.assertEqual({path.name: path.read_bytes() for path in outside.iterdir()}, original)
        self.assertFalse((consumer.root.parent / "oracle-executed").exists())

    def test_a04_wrong_commit_and_corrupt_archive_cannot_run_the_reviewer(self):
        consumer = self.consumer
        candidate = consumer.editorial_candidate()
        outside = consumer.root.parent / "outside-marker"
        outside.write_bytes(b"original")
        transport = support.TRANSPORT.replace("def invoke(", ARCHIVE_ATTACK + "\ndef invoke(").replace(
            "    return real_run(command, *args, **kwargs)",
            """    variant = os.environ["KDD_ATTACK"]
    if variant == "wrong" and "fetch" in command:
        command[-1] = os.environ["KDD_ALTERNATE_PIN"]
    result = real_run(command, *args, **kwargs)
    if not result.returncode and "archive" in command:
        archive = next(Path(arg.removeprefix("--output=")) for arg in command if arg.startswith("--output="))
        alter_archive(archive, variant)
    return result""",
        )
        for variant, diagnostic in (
            ("wrong", "does not match commit"), ("blob", "blob differs"), ("omit", "omits Git blob"),
            ("duplicate", "Unexpected entry"), ("link", "Unexpected entry"), ("escape", "Unexpected entry"),
        ):
            with self.subTest(variant=variant), patch.object(support, "TRANSPORT", transport):
                process = consumer.invoke("entry", consumer.root / ".kdd/validate.py", (
                    "review", "--approved-ref", consumer.approved, "--base-ref", consumer.approved,
                    "--candidate-ref", candidate,
                ), settings={
                    "KDD_ATTACK": variant, "KDD_ALTERNATE_PIN": consumer.second,
                    **dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(consumer.root.parent)),
                })
                self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
                self.assertEqual(process.stdout, "")
                self.assertIn(diagnostic, process.stderr)
                self.assertEqual(outside.read_bytes(), b"original")
                self.assertFalse((consumer.root.parent / "oracle-executed").exists())

    def test_a16_candidate_step_cannot_replace_the_approved_step(self):
        consumer = self.consumer
        workflow = deepcopy(consumer.workflow)
        step = {"name": "Validate the selected contracts", "shell": "python -I {0}",
                "run": "print('candidate reports success without running the gate')"}
        workflow["jobs"]["validate"]["steps"] = [step]
        self.assertEqual(workflow["name"], consumer.workflow["name"])
        self.assertEqual(workflow["jobs"]["validate"].get("name"),
                         consumer.workflow["jobs"]["validate"].get("name"))
        standalone = subprocess.run([sys.executable, "-I", "-c", step["run"]], cwd=consumer.root,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(standalone.returncode, 0, standalone.stderr)
        path = ".github/workflows/kdd-validate.yml"
        consumer.write(path, yaml.safe_dump(workflow).encode("utf-8"))
        consumer.commit("Substitute the candidate workflow while retaining its name")
        checked = trusted.TrustedAdoptionPullRequestTests.run_step(consumer, consumer.approved)
        self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
        self.assertIn(path, checked.stdout + checked.stderr)
        self.assertFalse((consumer.root.parent / "oracle-executed").exists())
