"""Run validate.py with packages installed by the actual pip."""
import hashlib
import unittest
import zipfile

from tests.adoption_remediation_support import AdoptionIntegration


class AdoptionPythonEnvironmentTests(AdoptionIntegration, unittest.TestCase):
    def require_wheel(self, valid_hash=True):
        dist = "kdd_fixture_dependency-0.0.1.dist-info/"
        path = self.root / "wheels/kdd_fixture_dependency-0.0.1-py3-none-any.whl"
        path.parent.mkdir()
        files = {
            "audit_dependency.py": "value = 'installed via the approved hash'\n",
            dist + "METADATA": "Metadata-Version: 2.1\nName: kdd-fixture-dependency\nVersion: 0.0.1\n",
            dist + "WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        }
        files[dist + "RECORD"] = "\n".join(name + ",," for name in (*files, dist + "RECORD")) + "\n"
        with zipfile.ZipFile(path, "w") as wheel:
            for name, text in files.items():
                wheel.writestr(name, text)
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if valid_hash else "0" * 64
        lock = "--no-index\n--find-links ./wheels\nkdd-fixture-dependency==0.0.1 --hash=sha256:" + digest + "\n"
        self.write("requirements-kdd.txt", lock.encode("ascii"))
        oracle = "tests/test_product.py"
        original = (self.root / oracle).read_bytes()
        replacement = original.replace(
            b"from product import label",
            b"from product import label\nfrom audit_dependency import value",
        ).replace(
            b"        self.assertEqual(label",
            b"        self.assertEqual(value, 'installed via the approved hash')\n"
            b"        self.assertEqual(label",
        )
        self.assertNotEqual(original, replacement)
        self.write(oracle, replacement)
        contract = "knowledge/contracts/label.md"
        updated = (self.root / contract).read_bytes().replace(
            hashlib.sha256(original).hexdigest().encode(),
            hashlib.sha256(replacement).hexdigest().encode(),
        )
        self.write(contract, updated)

    def test_installs_locked_dependency_in_a_temporary_venv(self):
        self.require_wheel()
        self.install(("--requirements-file", "requirements-kdd.txt"))
        self.commit("Approve the hashed dependency and adoption")
        run = self.launch()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["executed_tests"], 1)
        self.assertTrue((self.root.parent / "oracle-executed").is_file())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_rejects_bad_dependency_hash_before_executing_the_oracle(self):
        self.require_wheel(valid_hash=False)
        self.install(("--requirements-file", "requirements-kdd.txt"))
        self.commit("Introduce an invalid dependency hash")
        run = self.launch()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["stage"], "prepare")
        self.assertIn("hash", (run.stdout + run.stderr).lower())
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def src_project(self):
        (self.root / "src").mkdir()
        (self.root / "product.py").rename(self.root / "src/product.py")
        contract = "knowledge/contracts/label.md"
        text = (self.root / contract).read_bytes()
        self.write(contract, text.replace(b"'product.py'", b"'src/product.py'"))
        self.write("pyproject.toml", b'[build-system]\nrequires = []\n'
                   b'build-backend = "fixture_backend"\nbackend-path = ["."]\n')
        self.write("fixture_backend.py", b"raise AssertionError('Candidate backend must not load')\n")

    def test_imports_src_layout_project_without_running_backend(self):
        self.src_project()
        self.install(("--source-dir", "src"))
        approved = self.commit("Approve the existing src-layout project")
        run = self.launch({"KDD_ADOPTION_APPROVED_REF": approved})
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["executed_tests"], 1)
        self.assertEqual(self.evidence(run)["oracle_passes"], [1, 1])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_plan_rejects_requirements_path_outside_consumer(self):
        external = self.root.parent / "requirements.txt"
        external.write_text("", encoding="utf-8")
        before = self.fixture.snapshot()
        run = self.installer("--plan", options=("--requirements-file", "../requirements.txt"))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("ADOPTION_", run.stderr)
        self.assertEqual(self.fixture.snapshot(), before)

    def test_candidate_cannot_replace_approved_dependency_lock(self):
        self.require_wheel()
        self.install(("--requirements-file", "requirements-kdd.txt"))
        approved = self.commit("Approve the hashed dependency")
        lock = "requirements-kdd.txt"
        self.write(lock, (self.root / lock).read_bytes() + b"# Candidate replacement\n")
        self.commit("Change an approved dependency file")
        run = self.launch({"KDD_ADOPTION_APPROVED_REF": approved})
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn(lock, run.stdout + run.stderr)
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_rejects_python_startup_module_in_candidate_source_path(self):
        self.src_project()
        self.install(("--source-dir", "src"))
        approved = self.commit("Approve the project before startup injection")
        marker = self.root.parent / "startup-ran"
        self.write("src/sitecustomize.py",
                   ("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n").encode())
        self.commit("Introduce a Python startup module in the source directory")
        run = self.launch({"KDD_ADOPTION_APPROVED_REF": approved})
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("sitecustomize", run.stdout + run.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root.parent / "oracle-executed").exists())

    def test_dependency_lock_cannot_include_another_manifest(self):
        self.require_wheel()
        name = "requirements-kdd.txt"
        self.write("nested.txt", (self.root / name).read_bytes())
        self.write(name, b"--requirement nested.txt\n")
        self.install(("--requirements-file", name))
        self.commit("Try to follow an undeclared manifest")
        run = self.launch()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertEqual(self.evidence(run)["stage"], "prepare")
        self.assertIn("--requirement", run.stdout + run.stderr)
        self.assertFalse((self.root.parent / "oracle-executed").exists())
