"""Tests del inicializador de plantilla KDD (Contrato 06 / I-INIT).

Cubren lo que lista la seccion Tests del task contract
``knowledge/contracts/init-project.md``: dry-run inocuo, apply exacto al
manifiesto, los 3 gates verdes post-apply en la copia, intocables presentes,
``--name`` solo el titulo, manifiesto incompleto aborta, exit codes del CLI.

Corren sobre una **copia temporal** del repo (sin ``.git``): el target
``scripts/init_project.py`` NO toca el repo real. Los tests PUEDEN usar
subprocess (patron estandar); el target es stdlib puro y sin subprocess.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "scripts", "init_project.py")

# Manifiesto importado del propio scripts/init_project.py (no se duplica la
# lista): si el repo real YA fue inicializado (--apply corrido sobre el arbol
# real), los artefactos de ejemplo del manifiesto desaparecen y estos tests esperan la
# plantilla integra -> fallarian. El guard de clase skipUnless abajo saltea
# toda la suite en ese caso; en la plantilla integra (8 presentes) corre.
_spec_init = importlib.util.spec_from_file_location("init_project", SCRIPT)
_init_mod = importlib.util.module_from_spec(_spec_init)
_spec_init.loader.exec_module(_init_mod)
MANIFEST = _init_mod.MANIFEST

# Intocables que deben seguir presentes post-apply (subset representative
# del listado del task contract).
INTACTABLES = (
    "scripts/validate_contracts.py",
    "scripts/validate_okf.py",
    "scripts/assemble_context.py",
    "scripts/export_gate_contract.py",
    "ccdd/context.json",
    ".agents/AGENTS.md",
    ".agents/skills/kdd-okf-ccdd-hybrid/SKILL.md",
    "specs/CONTRACT-06-init-project.md",
    "knowledge/OKF-SPEC.md",
    "knowledge/metodologia-ejecucion.md",
    "knowledge/contracts/assemble-context.md",
    "knowledge/contracts/agents-context-rule.md",
    "knowledge/contracts/validate-okf.md",
    "knowledge/contracts/export-gate-contract.md",
    "knowledge/contracts/init-project.md",
    ".github/workflows/validate.yml",
    "tests/test_agents_rules.py",
    "tests/test_assemble_context.py",
    "tests/test_export_gate_contract.py",
    "tests/test_validate_contracts.py",
    "tests/test_validate_okf.py",
)


def _ignore(src, names):
    # Replica de clon: ademas de .git/__pycache__/*.gate.md, .agents/logs/
    # esta gitignorado -> no existe en un clon fresco. Excluirlo hace la
    # copia fiel al clon (sin logs heredados) y ejercita el mkdir del helper
    # _tmpdir() del export gate test durante el discover de la copia.
    ignored = [n for n in names
               if n in (".git", "__pycache__") or n.endswith(".gate.md")]
    if os.path.basename(src) == ".agents":
        ignored.append("logs")
    return ignored


def _copy_repo(dst):
    shutil.copytree(ROOT, dst, ignore=_ignore, dirs_exist_ok=True)


def _files(root):
    """Conjunto de rutas relativas posix de archivos bajo root."""
    out = set()
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            out.add(rel.replace(os.sep, "/"))
    return out


def _run_cli(repo_dir, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, "--repo-dir", repo_dir, *args],
        capture_output=True, text=True, encoding="utf-8")


def _run(args, cwd):
    return subprocess.run([sys.executable, *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8")


@unittest.skipUnless(
    all(os.path.isfile(os.path.join(ROOT, rel)) for rel in MANIFEST),
    "plantilla ya inicializada: faltan artefactos del manifiesto de ejemplo")
class TestInitProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_no_modifica_nada(self):
        _copy_repo(self.repo)
        before = _files(self.repo)
        r = _run_cli(self.repo)  # sin --apply
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("dry-run", r.stdout.lower())
        after = _files(self.repo)
        self.assertEqual(before, after, "dry-run modifico el arbol")
        # el index tampoco se reescribio
        idx = Path(self.repo, "knowledge", "index.md")
        self.assertIn("data_models/users_table.md", idx.read_text(encoding="utf-8"))

    def test_apply_elimina_exactamente_el_manifiesto(self):
        _copy_repo(self.repo)
        before = _files(self.repo)
        r = _run_cli(self.repo, "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = _files(self.repo)
        self.assertEqual(before - after, set(MANIFEST),
                         "se elimino algo distinto al manifiesto: {}".format(
                             before - after))
        self.assertEqual(after - before, set(),
                         "apply creo archivos: {}".format(after - before))
        for rel in MANIFEST:
            self.assertFalse(os.path.isfile(os.path.join(self.repo, rel)),
                             "no se elimino: {}".format(rel))

    def test_gates_verdes_post_apply_en_copia(self):
        # Criterio estrella: post-init los 3 gates verdes en la copia.
        _copy_repo(self.repo)
        self.assertEqual(_run_cli(self.repo, "--apply").returncode, 0)
        vc = _run(["scripts/validate_contracts.py", "knowledge/contracts"], self.repo)
        self.assertEqual(vc.returncode, 0, "validate_contracts:\n" + vc.stdout + vc.stderr)
        vo = _run(["scripts/validate_okf.py", "knowledge"], self.repo)
        self.assertEqual(vo.returncode, 0, "validate_okf:\n" + vo.stdout + vo.stderr)
        # Evitar recursion: este mismo test no debe correrse dentro del
        # discover de la copia (no es "infra restante", es el test del tool).
        os.unlink(os.path.join(self.repo, "tests", "test_init_project.py"))
        disc = _run(["-m", "unittest", "discover", "-s", "tests",
                     "-p", "test_*.py"], self.repo)
        self.assertEqual(disc.returncode, 0,
                         "unittest discover:\n" + disc.stdout + disc.stderr)

    def test_intocables_presentes_post_apply(self):
        _copy_repo(self.repo)
        self.assertEqual(_run_cli(self.repo, "--apply").returncode, 0)
        for rel in INTACTABLES:
            self.assertTrue(os.path.exists(os.path.join(self.repo, rel)),
                            "intocable faltante post-apply: {}".format(rel))

    def test_name_reemplaza_solo_el_titulo_h1(self):
        _copy_repo(self.repo)
        before = Path(self.repo, "README.md").read_text(encoding="utf-8").split("\n")
        self.assertEqual(_run_cli(self.repo, "--apply", "--name",
                                  "Mi Proyecto").returncode, 0)
        after = Path(self.repo, "README.md").read_text(encoding="utf-8").split("\n")
        self.assertEqual(after[0], "# Mi Proyecto")
        self.assertEqual(after[1:], before[1:],
                         "--name modifico mas que el titulo H1")

    def test_manifiesto_incompleto_aborta_sin_tocar_nada(self):
        _copy_repo(self.repo)
        before = _files(self.repo)
        os.unlink(os.path.join(self.repo, "src", "users.py"))
        r = _run_cli(self.repo, "--apply")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(_files(self.repo), before - {"src/users.py"},
                         "aborto pero toco archivos")

    def test_exit_code_0_dry_run(self):
        _copy_repo(self.repo)
        self.assertEqual(_run_cli(self.repo).returncode, 0)

    def test_exit_code_0_apply(self):
        _copy_repo(self.repo)
        self.assertEqual(_run_cli(self.repo, "--apply").returncode, 0)

    def test_exit_code_2_manifiesto_incompleto(self):
        _copy_repo(self.repo)
        os.unlink(os.path.join(self.repo, "knowledge", "contracts",
                               "validate-user-record.md"))
        self.assertEqual(_run_cli(self.repo, "--apply").returncode, 2)

    def test_exit_code_1_io(self):
        # Manifiesto completo pero knowledge/index.md ilegible/ausente ->
        # OSError al reescribir -> exit 1 (I/O).
        _copy_repo(self.repo)
        os.unlink(os.path.join(self.repo, "knowledge", "index.md"))
        r = _run_cli(self.repo, "--apply")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()