"""Exercise the adopter and generated workflow with Git and Python subprocesses."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from tests import test_adopt_project as original

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/adopt_project.py"
OFFICIAL_ORIGIN = "https://github.com/MauricioPerera/KDD.git"
MANAGED = tuple(original.GENERATED)
POLICY = "quality/product.json"

TRANSPORT = r"""
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch

source, mode, entry, *arguments = sys.argv[1:]
real_run = subprocess.run
harness = os.environ["KDD_TEST_TRANSPORT"]
origin = "https://github.com/MauricioPerera/KDD.git"

def invoke(argv, *args, **kwargs):
    command = list(argv)
    if "fetch" in command and origin in command:
        command[command.index(origin)] = source
    if mode == "workflow" and command[0] == sys.executable:
        for index, item in enumerate(command[1:], 1):
            if str(item).endswith("validate.py"):
                command = [*command[:index], "-c", harness, source, "entry", *command[index:]]
                break
    return real_run(command, *args, **kwargs)

sys.argv = [entry, *arguments]
if mode == "installer":
    sys.path.insert(0, str(Path(entry).parent))
with patch.object(subprocess, "run", invoke):
    runpy.run_path(entry, run_name="__main__")
"""


class AdoptionIntegration:
    def setUp(self):
        self.fixture = original.AdoptExistingProjectTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root
        self.git = self.fixture.git
        self.write = self.fixture.write
        self.seed, self.first, self.second = self.seed_repository()

    def seed_repository(self):
        seed = self.root.parent / "reviewed runtime"
        seed.mkdir()
        scripts = seed / "scripts"
        scripts.mkdir()
        for module in (
            "validate_contracts", "validate_okf", "validate_test_commands",
            "validate_baseline", "verify_quality", "oracle_execution", "oracle_inventory",
            "validation_runtime", "process_tree", "unittest_oracle_runner",
        ):
            shutil.copyfile(ROOT / "scripts" / (module + ".py"), scripts / (module + ".py"))

        def git(*args):
            return subprocess.check_output(["git", "-C", str(seed), *args],
                                           encoding="utf-8", timeout=30).strip()

        git("init", "--quiet", "--initial-branch=main", "--template=")

        def revision(marker):
            (seed / "revision.txt").write_text(marker, encoding="ascii")
            git("add", ".")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "-qm", marker)
            return git("rev-parse", "HEAD")

        return seed, revision("KDD A"), revision("KDD B")

    def commit(self, message):
        self.git("add", "-A")
        self.fixture.commit(message)
        return self.git("rev-parse", "HEAD")

    def invoke(self, mode, entry, arguments=(), settings=None):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("KDD_", "GITHUB_", "RUNNER_"))}
        env["KDD_TEST_TRANSPORT"] = TRANSPORT
        env["KDD_ADOPTION_TEST_SENTINEL"] = str(self.root.parent / "oracle-executed")
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
        env.update(settings or {})
        return subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-B", "-c", TRANSPORT,
             str(self.seed), mode, str(entry), *arguments],
            cwd=self.root, env=env, capture_output=True, encoding="utf-8",
            errors="replace", timeout=150,
        )

    def installer(self, mode="--apply", pin=None, options=()):
        return self.invoke("installer", INSTALLER, (
            "--repo-root", str(self.root), "--contracts-dir", "knowledge/contracts",
            "--validator-commit", self.first if pin is None else pin, mode, *options,
        ))

    def install(self, options=()):
        result = self.installer(options=options)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def launch(self, settings=None):
        return self.invoke("entry", self.root / ".kdd/validate.py", settings=settings)

    def evidence(self, process):
        records = [json.loads(line.removeprefix("KDD_PILOT ")) for line in process.stdout.splitlines()
                   if line.startswith("KDD_PILOT ")]
        self.assertEqual(len(records), 1, process.stdout + process.stderr)
        return records[0]

    def policy(self, name=POLICY, helper=True):
        policy = {
            "protected": ["tests/test_product.py", "tests/__init__.py"],
            "implementation": ["product.py"],
            "pm": [],
            "required_kinds": ["functional", "adversarial"],
            "checks": [
                {"name": kind, "kind": kind, "timeout": 20,
                 "argv": ["python", "-B", "-m", "unittest", "tests.test_product"]}
                for kind in ("functional", "adversarial")
            ],
        }
        self.write(name, (json.dumps(policy) + "\n").encode())
        if helper:
            self.write("scripts/process_tree.py", (ROOT / "scripts/process_tree.py").read_bytes())
