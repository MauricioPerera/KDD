"""Integration contract for adding KDD to a repository that already exists."""

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


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "adopt_project.py"
PIN = "e07e404b4a8576f26cf9b6d3628f7ce5cd8ccaa8"
OTHER_PIN = "3cc5948dc0cf151519dbe8b595c30d7947159336"
CONTRACTS = "knowledge/contracts"
GENERATED = sorted([
    ".github/workflows/kdd-validate.yml",
    ".kdd/validate.py",
    ".kdd/validator.lock",
])


class AdoptExistingProjectTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix="kdd-adoption-")
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name) / "existing project"
        self.root.mkdir()
        self.git("init", "--quiet", "--initial-branch=main", "--template=")
        self.write("product.py", b"def label(text):\n    return text.strip().lower()\n")
        oracle = (
            b"import unittest\nimport os\nfrom pathlib import Path\nfrom product import label\n\n"
            b"class LabelTest(unittest.TestCase):\n"
            b"    def test_normalizes(self):\n"
            b"        if os.environ.get('KDD_ADOPTION_TEST_SENTINEL'):\n"
            b"            Path(os.environ['KDD_ADOPTION_TEST_SENTINEL']).write_text('executed')\n"
            b"        self.assertEqual(label('  Demo '), 'demo')\n"
        )
        self.write("tests/__init__.py", b"")
        self.write("tests/test_product.py", oracle)
        self.write(".github/workflows/product.yml", b"name: Product\non: [push]\n")
        self.write("knowledge/index.md", b"# Knowledge\n\n- [Label](contracts/label.md)\n")
        self.write(
            f"{CONTRACTS}/label.md",
            (
                "---\ntype: 'Task Contract'\ntitle: 'Label'\ndescription: 'Normalize the label.'\n"
                "tags: ['product']\ntask: label\nintent: 'Normalize the label.'\n"
                "target: 'product.py'\nsignature: 'def label(text):'\n"
                "tests: 'tests/test_product.py'\n"
                "test_command: 'python -m unittest tests/test_product.py'\n"
                "test_runner: python-unittest\noracle_files: ['tests/test_product.py']\n"
                f"tests_sha256: '{hashlib.sha256(oracle).hexdigest()}'\n"
                "budget:\n  cyclomatic_max: 4\ntouch_only: ['product.py']\n"
                "deps_allowed: []\nforbids: ['network']\n---\n\n"
                "## Intent\nNormalize the label.\n\n## Interface\nlabel(text)\n\n"
                "## Invariants\n- Strip spaces.\n\n## Examples\n- ' A ' -> 'a'.\n"
                "- 'B' -> 'b'.\n\n## Do / Don't\n- DO preserve input order.\n\n"
                "## Tests\nExecute the existing test.\n\n## Constraints\n"
                "PARAR y reportar si el oráculo cambia.\n"
            ).encode("utf-8"),
        )
        self.git("add", ".")
        self.commit("Existing project and reviewed contract")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, encoding="utf-8", timeout=30).stdout.strip()

    def commit(self, message):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", message)

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def snapshot(self):
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes() if path.is_file() else None
            for path in self.root.rglob("*") if ".git" not in path.relative_to(self.root).parts
        }

    def args(self, mode, *, pin=PIN, contracts=CONTRACTS, root=None):
        return ["--repo-root", str(self.root if root is None else root),
                "--contracts-dir", contracts, "--validator-commit", pin, mode]

    def run_cli(self, mode, **kwargs):
        return subprocess.run([sys.executable, "-B", str(CLI), *self.args(mode, **kwargs)],
                              capture_output=True, encoding="utf-8", timeout=30)

    def success(self, process):
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return json.loads(process.stdout)

    def failure(self, process, code):
        self.assertNotEqual(process.returncode, 0)
        self.assertIn(code, process.stdout + process.stderr)

    def test_preview_lists_only_managed_files_and_does_not_write(self):
        before = self.snapshot()
        result = self.success(self.run_cli("--plan"))
        self.assertEqual(result, {"status": "planned", "create": GENERATED, "keep": []})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_apply_preserves_existing_sources_and_ci(self):
        before = self.snapshot()
        result = self.success(self.run_cli("--apply"))
        self.assertEqual(result, {"status": "applied", "create": GENERATED, "keep": []})
        after = self.snapshot()
        self.assertEqual({key: after[key] for key in before}, before)
        self.assertEqual(sorted(key for key in after.keys() - before.keys() if after[key] is not None), GENERATED)
        self.assertEqual(after[".kdd/validator.lock"], (PIN + "\n").encode("ascii"))
        workflow = after[".github/workflows/kdd-validate.yml"].decode("utf-8")
        data = yaml.load(workflow, Loader=yaml.BaseLoader)
        self.assertIn("push", data["on"])
        self.assertEqual(data["permissions"], {"contents": "read"})
        self.assertEqual(len(data["jobs"]), 1)
        job = next(iter(data["jobs"].values()))
        self.assertEqual(job["strategy"]["matrix"], {"os": ["ubuntu-latest", "windows-latest"]})
        self.assertEqual(job["runs-on"], "${{ matrix.os }}")
        for prohibited in ("if", "needs", "continue-on-error", "permissions"):
            self.assertNotIn(prohibited, job)
        steps = job["steps"]
        self.assertTrue(all("if" not in step and "continue-on-error" not in step for step in steps))
        checkout = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
        python = [step for step in steps if step.get("uses", "").startswith("actions/setup-python@")]
        self.assertEqual(len(checkout), 1)
        self.assertEqual(len(python), 1)
        self.assertRegex(checkout[0]["uses"], r"^actions/checkout@[0-9a-f]{40}$")
        self.assertRegex(python[0]["uses"], r"^actions/setup-python@[0-9a-f]{40}$")
        self.assertEqual(checkout[0]["with"]["ref"], "${{ github.sha }}")
        self.assertEqual(checkout[0]["with"]["persist-credentials"], "false")
        self.assertEqual(python[0]["with"]["python-version"], "3.11")
        validation = [step for step in steps if step.get("run", "").strip() == "python .kdd/validate.py"]
        self.assertEqual(len(validation), 1)
        self.assertLess(steps.index(checkout[0]), steps.index(validation[0]))
        self.assertLess(steps.index(python[0]), steps.index(validation[0]))
        self.assertNotIn(PIN, workflow)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")

    def test_reapply_keeps_bytes_and_mtimes(self):
        self.success(self.run_cli("--apply"))
        before = {name: (self.root / name).stat().st_mtime_ns for name in GENERATED}
        raw = self.snapshot()
        self.assertEqual(self.success(self.run_cli("--apply")),
                         {"status": "unchanged", "create": [], "keep": GENERATED})
        self.assertEqual(self.snapshot(), raw)
        self.assertEqual({name: (self.root / name).stat().st_mtime_ns for name in GENERATED}, before)

    def test_reapply_accepts_crlf_checkout_without_rewriting(self):
        self.success(self.run_cli("--apply"))
        for name in GENERATED:
            path = self.root / name
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        before = self.snapshot()
        self.assertEqual(self.success(self.run_cli("--apply"))["status"], "unchanged")
        self.assertEqual(self.snapshot(), before)

    def test_partial_install_keeps_identical_lock(self):
        self.write(".kdd/validator.lock", (PIN + "\n").encode("ascii"))
        lock = self.root / ".kdd/validator.lock"
        modified = lock.stat().st_mtime_ns
        result = self.success(self.run_cli("--apply"))
        self.assertEqual(result["keep"], [".kdd/validator.lock"])
        self.assertEqual(result["create"], sorted(set(GENERATED) - set(result["keep"])))
        self.assertEqual(lock.stat().st_mtime_ns, modified)

    def test_different_pin_is_a_conflict_and_preserves_the_existing_install(self):
        self.success(self.run_cli("--apply"))
        before = self.snapshot()
        self.failure(self.run_cli("--apply", pin=OTHER_PIN), "ADOPTION_CONFLICT")
        self.assertEqual(self.snapshot(), before)

    def test_workflow_collision_stops_the_whole_application(self):
        self.write(".github/workflows/kdd-validate.yml", b"name: Existing workflow\n")
        before = self.snapshot()
        for mode in ("--plan", "--apply"):
            result = self.run_cli(mode)
            self.failure(result, "ADOPTION_CONFLICT")
            self.assertIn(".github/workflows/kdd-validate.yml", result.stdout + result.stderr)
            self.assertEqual(self.snapshot(), before)

    def test_non_directory_ancestor_is_rejected_without_writes(self):
        self.write(".kdd", b"already a file")
        before = self.snapshot()
        self.failure(self.run_cli("--apply"), "ADOPTION_PATH")
        self.assertEqual(self.snapshot(), before)

    def test_rejects_invalid_sha_before_creating_files(self):
        before = self.snapshot()
        for bad in ("main", PIN[:12], PIN + " "):
            with self.subTest(pin=bad):
                self.failure(self.run_cli("--apply", pin=bad), "ADOPTION_PIN")
                self.assertEqual(self.snapshot(), before)

    def test_rejects_contract_directory_outside_scope_or_missing(self):
        before = self.snapshot()
        for directory in ("../outside", "tests", "knowledge/contracts/missing"):
            with self.subTest(contracts=directory):
                self.failure(self.run_cli("--apply", contracts=directory), "ADOPTION_CONTRACTS")
                self.assertEqual(self.snapshot(), before)

    def test_rejects_a_subdirectory_instead_of_the_git_root(self):
        before = self.snapshot()
        result = self.run_cli("--apply", root=self.root / "knowledge")
        self.failure(result, "ADOPTION_ROOT")
        self.assertEqual(self.snapshot(), before)

    def test_preserves_unrelated_unstaged_and_staged_edits(self):
        self.write("product.py", b"def label(text):\n    return text.lower()\n")
        self.write("work-in-progress.txt", b"pending user edit")
        self.git("add", "work-in-progress.txt")
        before = self.snapshot()
        status = self.git("diff", "--cached", "--name-status")
        self.success(self.run_cli("--apply"))
        after = self.snapshot()
        self.assertEqual({key: after[key] for key in before}, before)
        self.assertEqual(self.git("diff", "--cached", "--name-status"), status)

    def test_write_failure_recovers_the_managed_tree(self):
        # Fail the second creation after a real first write, without changing OS permissions.
        harness = """
import errno
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
target = Path(sys.argv[1]).resolve()
entry = sys.argv[2]
original = Path.open
creations = []
def fail(path, mode='r', *args, **kwargs):
    if 'x' in mode and path.resolve().is_relative_to(target) and '.git' not in path.parts:
        creations.append(path)
        if len(creations) == 2:
            with original(path, mode, *args, **kwargs) as partial:
                partial.write(b'partial bytes')
            print('INJECTED_SECOND_WRITE', file=sys.stderr)
            raise OSError(errno.EIO, 'simulated write failure', str(path))
    return original(path, mode, *args, **kwargs)
sys.path.insert(0, str(Path(entry).parent))
sys.argv = [entry, *sys.argv[3:]]
with patch.object(Path, 'open', fail):
    runpy.run_path(entry, run_name='__main__')
"""
        before = self.snapshot()
        process = subprocess.run(
            [sys.executable, "-B", "-c", harness, str(self.root), str(CLI), *self.args("--apply")],
            capture_output=True, encoding="utf-8", timeout=30,
        )
        self.failure(process, "ADOPTION_WRITE")
        self.assertIn("INJECTED_SECOND_WRITE", process.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.success(self.run_cli("--apply"))


    def test_deleted_managed_path_preserves_index_and_absence(self):
        self.success(self.run_cli("--apply"))
        self.git("add", "--", *GENERATED)
        self.commit("Existing KDD files")
        name = ".kdd/validate.py"
        for staged in (False, True):
            with self.subTest(staged=staged):
                (self.root / name).unlink()
                if staged:
                    self.git("add", "-u", "--", name)
                before = self.git("status", "--porcelain")
                for mode in ("--plan", "--apply"):
                    self.failure(self.run_cli(mode), "ADOPTION_CONFLICT")
                    self.assertFalse((self.root / name).exists())
                    self.assertEqual(self.git("status", "--porcelain"), before)
                self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", name)

    def test_managed_destination_directory_is_not_changed(self):
        relative = ".kdd/validate.py"
        self.write(relative + "/keep.txt", b"not a launcher")
        before = self.snapshot()
        for mode in ("--plan", "--apply"):
            self.failure(self.run_cli(mode), "ADOPTION_PATH")
            self.assertEqual(self.snapshot(), before)

    def test_linked_ancestor_cannot_write_outside_the_repository(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"external")
        link = self.root / ".kdd"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                           capture_output=True, check=True, timeout=15)
        try:
            before = self.git("status", "--porcelain")
            for mode in ("--plan", "--apply"):
                self.failure(self.run_cli(mode), "ADOPTION_PATH")
                self.assertEqual(self.git("status", "--porcelain"), before)
                self.assertEqual(list(outside.iterdir()), [outside / "keep.txt"])
                self.assertEqual((outside / "keep.txt").read_bytes(), b"external")
        finally:
            if link.is_symlink():
                link.unlink()
            else:
                link.rmdir()

    def test_nested_contract_directory_and_template_only_rejection(self):
        nested = CONTRACTS + "/product"
        (self.root / nested).mkdir()
        (self.root / CONTRACTS / "label.md").rename(self.root / nested / "TEMPLATE-label.md")
        before = self.snapshot()
        self.failure(self.run_cli("--plan", contracts=nested), "ADOPTION_CONTRACTS")
        self.assertEqual(self.snapshot(), before)
        (self.root / nested / "TEMPLATE-label.md").rename(self.root / nested / "label.md")
        self.write("knowledge/index.md", b"# Knowledge\n\n- [Label](contracts/product/label.md)\n")
        self.success(self.run_cli("--apply", contracts=nested))
        seed, pin, _ = self.validator_repository()
        self.write(".kdd/validator.lock", (pin + "\n").encode("ascii"))
        self.assertEqual(self.launch(seed).returncode, 0)

    def validator_repository(self):
        seed = self.root.parent / "validator source"
        seed.mkdir()

        def git(*args):
            return subprocess.run(["git", "-C", str(seed), *args], check=True,
                                  capture_output=True, encoding="utf-8", timeout=30).stdout.strip()

        git("init", "--quiet", "--initial-branch=main", "--template=")
        (seed / "scripts").mkdir()
        for name in (
            "validate_contracts.py", "validate_okf.py", "validate_test_commands.py",
            "oracle_execution.py", "oracle_inventory.py", "validation_runtime.py",
            "process_tree.py", "unittest_oracle_runner.py",
        ):
            shutil.copyfile(ROOT / "scripts" / name, seed / "scripts" / name)

        def revision(label):
            (seed / "runtime-fixture.txt").write_bytes(label)
            git("add", ".")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Runtime " + label.decode().strip())
            return git("rev-parse", "HEAD")

        return seed, revision(b"test-runtime-alpha\n"), revision(b"test-runtime-bravo\n")

    def launch(self, seed, alteration=""):
        # Only transport changes. Object fetching, archive extraction and the KDD
        # validators use real Git, files and Python subprocesses.
        harness = """
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch

seed, alteration, entry = sys.argv[1:]
os.environ.pop("KDD_QUALITY_APPROVED_REF", None)
os.environ["KDD_ADOPTION_TEST_SENTINEL"] = str(Path(seed).parent / "oracle-executed")
original = subprocess.run

def transport(argv, *args, **kwargs):
    call = list(argv)
    origin = "https://github.com/MauricioPerera/KDD.git"
    if "fetch" in call and origin in call:
        call[call.index(origin)] = seed
        if alteration == "missing":
            call[-1] = "f" * 40
        if alteration.startswith("wrong:"):
            call[-1] = alteration.split(":", 1)[1]
    result = original(call, *args, **kwargs)
    if alteration == "blob" and "archive" in call and result.returncode == 0:
        destination = next(Path(arg.removeprefix("--output=")) for arg in call if arg.startswith("--output="))
        content = destination.read_bytes()
        before = b"test-runtime-alpha" + bytes([10])
        after = b"test-runtime-alphx" + bytes([10])
        if before not in content:
            raise AssertionError("Fixture blob missing from the Git archive")
        destination.write_bytes(content.replace(before, after, 1))
    return result

sys.argv = [entry]
with patch.object(subprocess, "run", transport):
    runpy.run_path(entry, run_name="__main__")
"""
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-B", "-c", harness, str(seed), alteration,
             str(self.root / ".kdd/validate.py")],
            cwd=self.root, capture_output=True, encoding="utf-8", timeout=90,
        )

    def evidence(self, process, status, *, sha=None, stage=None):
        self.assertEqual(process.returncode == 0, status == "pass", process.stdout + process.stderr)
        records = [line.removeprefix("KDD_PILOT ") for line in process.stdout.splitlines()
                   if line.startswith("KDD_PILOT ")]
        self.assertEqual(len(records), 1, process.stdout + process.stderr)
        record = json.loads(records[0])
        self.assertEqual(record["result"], status)
        self.assertEqual(record.get("verified_kdd_sha"), sha)
        if stage is not None:
            self.assertEqual(record["stage"], stage)
        return record

    def test_installed_entry_selects_two_real_git_pins_and_detects_regression(self):
        seed, first, second = self.validator_repository()
        self.success(self.run_cli("--apply", pin=first))
        for pin in (first, second, first):
            with self.subTest(pin=pin):
                self.write(".kdd/validator.lock", (pin + "\n").encode("ascii"))
                record = self.evidence(self.launch(seed), "pass", sha=pin, stage="complete")
                self.assertEqual(record["requested_kdd_sha"], pin)
                self.assertEqual(record["executed_tests"], 1)
        original = (self.root / "product.py").read_bytes()
        self.write("product.py", b"def label(text):\n    return 'regression'\n")
        failure = self.launch(seed)
        self.evidence(failure, "fail", sha=first, stage="oracle")
        self.assertIn("AssertionError", failure.stdout + failure.stderr)
        self.write("product.py", original)
        self.evidence(self.launch(seed), "pass", sha=first, stage="complete")

    def test_installed_entry_fails_closed_on_git_identity_and_blob_changes(self):
        seed, first, second = self.validator_repository()
        self.success(self.run_cli("--apply", pin=first))
        for alteration in ("missing", "wrong:" + second, "blob"):
            with self.subTest(alteration=alteration):
                record = self.evidence(self.launch(seed, alteration), "fail", stage="resolve")
                self.assertEqual(record["requested_kdd_sha"], first)
                self.assertNotIn("executed_tests", record)

    def test_installed_entry_rejects_changed_seal_and_missing_quality_reference(self):
        seed, first, _ = self.validator_repository()
        self.success(self.run_cli("--apply", pin=first))
        self.evidence(self.launch(seed), "pass", sha=first, stage="complete")
        sentinel = self.root.parent / "oracle-executed"
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "executed")
        sentinel.unlink()
        name = CONTRACTS + "/label.md"
        old = (self.root / name).read_bytes()
        oracle = (self.root / "tests/test_product.py").read_bytes()
        invalid = old.replace(hashlib.sha256(oracle).hexdigest().encode("ascii"), b"0" * 64)
        self.assertNotEqual(old, invalid)
        self.write(name, invalid)
        self.evidence(self.launch(seed), "fail", sha=first, stage="contract")
        self.assertFalse((self.root.parent / "oracle-executed").exists())
        self.write(name, old)
        policy_data = {
            "protected": ["tests/test_product.py"],
            "implementation": ["product.py"],
            "pm": [],
            "required_kinds": ["functional", "adversarial"],
            "checks": [
                {"name": kind, "kind": kind,
                 "argv": ["python", "-m", "unittest", "tests/test_product.py"], "timeout": 30}
                for kind in ("functional", "adversarial")
            ],
        }
        for policy in ("quality.json", "quality/product.json"):
            self.write(policy, (json.dumps(policy_data) + "\n").encode("utf-8"))
            result = self.launch(seed)
            self.evidence(result, "fail", sha=first, stage="quality")
            self.assertIn("KDD_QUALITY_APPROVED_REF", result.stdout + result.stderr)
            self.assertFalse((self.root.parent / "oracle-executed").exists())
            (self.root / policy).unlink()

    def test_installed_entry_rejects_zero_contracts_after_adoption(self):
        seed, first, _ = self.validator_repository()
        self.success(self.run_cli("--apply", pin=first))
        contract = self.root / CONTRACTS / "label.md"
        template = contract.with_name("TEMPLATE-label.md")
        contract.rename(template)
        self.write("knowledge/index.md", b"# Knowledge\n\n- [Template](contracts/TEMPLATE-label.md)\n")
        control = subprocess.run([sys.executable, str(ROOT / "scripts/validate_okf.py"),
                                  str(self.root / "knowledge")], capture_output=True, encoding="utf-8")
        self.assertEqual(control.returncode, 0, control.stdout + control.stderr)
        self.evidence(self.launch(seed), "fail", sha=first, stage="contract")
        self.assertFalse((self.root.parent / "oracle-executed").exists())
        template.unlink()
        self.write("knowledge/index.md", b"# Knowledge\n")
        control = subprocess.run([sys.executable, str(ROOT / "scripts/validate_okf.py"),
                                  str(self.root / "knowledge")], capture_output=True, encoding="utf-8")
        self.assertEqual(control.returncode, 0, control.stdout + control.stderr)
        self.evidence(self.launch(seed), "fail", sha=first, stage="contract")
        self.assertFalse((self.root.parent / "oracle-executed").exists())
