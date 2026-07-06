"""Tests del exportador gate-nativo (CCDD nivel 2).

Cubre: normalizacion ASCII total, tabla de mapeos tipograficos, reescritura
de rutas ``target``/``tests`` relativas al export, determinismo byte a byte,
frontmatter preservado en claves y orden, export del contrato real de C04
(``validate-user-record.md``) con rutas que resuelven a archivos existentes,
y exit codes del CLI.

El target es stdlib puro y sin subprocess; los tests del CLI SI usan
subprocess (es lo unico permitido). Task contract:
``knowledge/contracts/export-gate-contract.md``.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "export_gate_contract.py"
# Los temp dirs van bajo .agents/logs (gitignorado, mismo drive que el repo):
# os.path.relpath no cruza mounts en Windows, y el contrato reescribe rutas
# relativas al out_dir, que en uso real vive dentro del repo.
_TMP_PARENT = ROOT / ".agents" / "logs"


def _tmpdir():
    # .agents/logs/ esta gitignorado -> no existe en un clon fresco. Crearlo
    # bajo demanda (2 lineas, cero cambio de logica) evita FileNotFoundError
    # al abrir el TemporaryDirectory. Inocuo cuando ya existe.
    _TMP_PARENT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=str(_TMP_PARENT))

# Carga del modulo por ruta (scripts/ no es paquete).
_spec = importlib.util.spec_from_file_location("export_gate_contract", SCRIPT)
egc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(egc)


# Contrato minimal de prueba (frontmatter valido + cuerpo con tipograficos).
_TEMPLATE = """---
type: 'Task Contract'
title: 'Test export'
task: {task}
intent: "probar"
target: src/users.py
signature: "def f(x):"
test_command: "python -m unittest tests/test_users.py"
budget:
  max_cyclomatic_complexity: 10
tests: "tests/test_users.py"
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: {task}

## Intent
- acentos: áéíóú ñ ÁÉÍÓÚ Ñ
- dashes: a — b – c ‒ d
- arrow: x → y
- comparadores: ≤ y ≥
- comillas: “curvas” ‘simples’
- bullets: • ‣ ·
"""


def _write_contract(dir_path: Path, task: str = "probe") -> Path:
    path = dir_path / "{}.md".format(task)
    path.write_text(_TEMPLATE.format(task=task), encoding="utf-8")
    return path


def _fm_values(text: str):
    """Devuelve dict {key: value} y lista de claves en orden del frontmatter."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == "---"), None)
    if start is None:
        return {}, []
    end = next((j for j in range(start + 1, len(lines))
                if lines[j].strip() == "---"), None)
    fm = lines[start + 1:end]
    values, keys = {}, []
    for ln in fm:
        s = ln.strip()
        if ":" not in s or s.startswith(" "):
            continue
        key, _, val = s.partition(":")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] in ("'", '"') and val[-1] == val[0]:
            val = val[1:-1]
        if key not in values:
            keys.append(key)
        values[key] = val
    return values, keys


class TestAsciiNormalization(unittest.TestCase):
    def test_export_is_pure_ascii(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "ascii")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            content = Path(out).read_text(encoding="ascii")
            self.assertTrue(all(ord(c) < 128 for c in content),
                            "salida tiene bytes no-ASCII")

    def test_accentos_nfkd_strip(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "accents")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            body = Path(out).read_text(encoding="ascii")
            self.assertIn("acentos: aeiou n AEIOU N", body)

    def test_explicit_table_mappings(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "maps")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            body = Path(out).read_text(encoding="ascii")
            self.assertIn("dashes: a - b - c - d", body)
            self.assertIn("arrow: x -> y", body)
            self.assertIn("comparadores: <= y >=", body)
            self.assertIn('comillas: "curvas" \'simples\'', body)
            self.assertIn("bullets: - - -", body)


class TestPathRewrite(unittest.TestCase):
    # Skip-guard (acoplamiento autorizado por C06): este test exporta un
    # contrato sintetico acoplado a src/users.py + tests/test_users.py reales
    # del repo; post-init esos ejemplos se eliminan -> se saltea limpio. En la
    # plantilla integra (fixtures presentes) sigue corriendo.
    @unittest.skipUnless(
        (ROOT / "src" / "users.py").is_file()
        and (ROOT / "tests" / "test_users.py").is_file(),
        "ejemplo removido por init: src/users.py o tests/test_users.py")
    def test_at_repo_root_no_dotdot_and_files_exist(self):
        # Default real: out_dir = raiz del repo. El gate rechaza rutas con
        # ".." (tc-tests-frozen); en la raiz las rutas quedan iguales a las
        # originales del contrato y resuelven a archivos existentes.
        # repo_root explicito (= ROOT): la convencion queda fijada por ruta
        # explicita, NO por el cwd de invocacion.
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "rootprobe")
            out = egc.export_gate_contract(str(src), str(ROOT),
                                            repo_root=str(ROOT))
            self.addCleanup(lambda p=Path(out): p.unlink(missing_ok=True))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            # sin ".." (lo que el gate real exige)
            self.assertNotIn("..", values["target"])
            self.assertNotIn("..", values["tests"])
            # iguales a las originales del contrato (raiz -> sin reescritura)
            self.assertEqual(values["target"], "src/users.py")
            self.assertEqual(values["tests"], "tests/test_users.py")
            # los archivos apuntados existen desde el export (en la raiz)
            export_dir = Path(out).resolve().parent
            self.assertTrue((export_dir / values["target"]).resolve().is_file())
            self.assertTrue((export_dir / values["tests"]).resolve().is_file())

    def test_custom_out_dir_rewrites_relative_to_export(self):
        # out_dir fuera de la raiz: la reescritura sigue calculandose relativa
        # al archivo de export (que vive bajo out_dir). Puede introducir "..".
        # repo_root explicito (= ROOT): el esperado se calcula contra esa
        # misma ruta explicita, no contra getcwd() — la convencion queda fijada.
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "rw")
            out_dir = d / "gate-exports"
            out = egc.export_gate_contract(str(src), str(out_dir),
                                          repo_root=str(ROOT))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            repo_root = str(ROOT)
            exp_target = os.path.relpath(
                os.path.join(repo_root, "src", "users.py"),
                str(out_dir)).replace(os.sep, "/")
            exp_tests = os.path.relpath(
                os.path.join(repo_root, "tests", "test_users.py"),
                str(out_dir)).replace(os.sep, "/")
            self.assertEqual(values["target"], exp_target)
            self.assertEqual(values["tests"], exp_tests)

    def test_output_independent_of_invocation_cwd(self):
        # T9: con --repo-root explicito, el export es INDEPENDIENTE del cwd
        # desde el que se invoque. Se construye un repo-fixture aislado (con
        # src/users.py + tests/test_users.py) para no depender de los ejemplo
        # del repo real (que init elimina). Se invoca la CLI dos veces con el
        # MISMO --repo-root pero desde cwds distintos -> bytes identicos.
        with _tmpdir() as d:
            d = Path(d)
            repo = d / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "src" / "users.py").write_text("x = 1\n", encoding="utf-8")
            (repo / "tests").mkdir(parents=True)
            (repo / "tests" / "test_users.py").write_text(
                "import unittest\n", encoding="utf-8")
            src = _write_contract(d, "cwdind")
            out_dir = d / "exports"
            elsewhere = d / "elsewhere"
            elsewhere.mkdir()
            common = [sys.executable, str(SCRIPT), str(src),
                      "--out-dir", str(out_dir), "--repo-root", str(repo)]
            r1 = subprocess.run(common, cwd=str(repo),
                                capture_output=True, text=True)
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertTrue(r1.stdout.strip(), r1.stderr)
            b1 = Path(r1.stdout.strip()).read_bytes()
            r2 = subprocess.run(common, cwd=str(elsewhere),
                                capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertTrue(r2.stdout.strip(), r2.stderr)
            b2 = Path(r2.stdout.strip()).read_bytes()
            self.assertEqual(b1, b2,
                             "export difiere segun cwd con --repo-root fijo")

    def test_rewritten_paths_use_posix_separator(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "posix")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            self.assertNotIn("\\", values["target"])
            self.assertNotIn("\\", values["tests"])


class TestDeterminism(unittest.TestCase):
    def test_two_exports_byte_identical(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "det")
            out1 = egc.export_gate_contract(str(src), str(d / "o1"))
            out2 = egc.export_gate_contract(str(src), str(d / "o2"))
            b1 = Path(out1).read_bytes()
            b2 = Path(out2).read_bytes()
            self.assertEqual(b1, b2, "dos exports del mismo input no son byte-identicos")

    def test_same_out_dir_overwrite_idempotent(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "idem")
            out_dir = d / "out"
            out1 = egc.export_gate_contract(str(src), str(out_dir))
            b1 = Path(out1).read_bytes()
            out2 = egc.export_gate_contract(str(src), str(out_dir))
            b2 = Path(out2).read_bytes()
            self.assertEqual(out1, out2)
            self.assertEqual(b1, b2)


class TestFrontmatterPreserved(unittest.TestCase):
    def test_keys_order_preserved_and_only_target_tests_test_command_change(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "fm")
            src_text = src.read_text(encoding="utf-8")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            out_text = Path(out).read_text(encoding="utf-8")

            src_vals, src_keys = _fm_values(src_text)
            out_vals, out_keys = _fm_values(out_text)

            # mismo orden de claves
            self.assertEqual(src_keys, out_keys)
            # target/tests/test_command cambian; el resto se preserva (ASCII)
            for k in src_keys:
                if k in ("target", "tests", "test_command"):
                    self.assertNotEqual(src_vals[k], out_vals[k])
                    continue
                self.assertEqual(egc._ascii_normalize(src_vals[k]), out_vals[k])

    def test_test_command_rewritten_relative_to_target_dir(self):
        # El gate ejecuta test_command con cwd = dir del target. El comando
        # reescrito apunta al archivo de tests relativo a ese dir (POSIX),
        # independientemente de out_dir (la relativa entre target y tests es
        # invariante al prefijo comun). Layout estandar del template:
        # target src/users.py, tests tests/test_users.py -> ../tests/test_users.py
        # El template declara "python -m unittest tests/test_users.py", que es
        # EXACTAMENTE el caso especial documentado (python -m unittest
        # <archivo>.py, 4 tokens): el export lo reescribe a invocacion directa
        # "python <rel>" SIN "-m unittest" (auto-ejecutable + -m unittest no
        # acepta rutas con "..").
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "tc")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            self.assertEqual(values["test_command"],
                             "python ../tests/test_users.py")
            self.assertNotIn("-m unittest", values["test_command"])
            # sin separador nativo (Windows backslash) colado
            self.assertNotIn("\\", values["test_command"])


class TestTestCommandRunnerPreserved(unittest.TestCase):
    # El runner de test_command se preserva del contrato fuente: NO se
    # hardcodea "python". Solo se reescribe la ruta del archivo de tests
    # (la aparicion literal del valor original de tests) a su equivalente
    # relativo al directorio del target (POSIX).

    _NODE_TEMPLATE = """---
type: 'Task Contract'
title: 'Test node runner'
task: {task}
intent: "probar runner node"
target: src/users.py
signature: "def f(x):"
test_command: "node --test tests/algo.test.mjs"
budget:
  max_cyclomatic_complexity: 10
tests: "tests/algo.test.mjs"
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: {task}

## Intent
- runner node preservado
"""

    _PY_REPO_TEMPLATE = """---
type: 'Task Contract'
title: 'Test python runner'
task: {task}
intent: "probar runner python del repo"
target: scripts/export_gate_contract.py
signature: "def f(x):"
test_command: "python -m unittest tests/test_export_gate_contract.py"
budget:
  max_cyclomatic_complexity: 10
tests: "tests/test_export_gate_contract.py"
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: {task}

## Intent
- runner python preservado
"""

    def test_node_runner_preserved_not_python(self):
        # (a) Contrato con runner node: el export debe conservar
        # "node --test <rel>" y NO contener "python". target en src/,
        # tests en tests/ -> rel "../tests/algo.test.mjs" (invariante al
        # prefijo comun: la relativa entre src/ y tests/ no depende de
        # out_dir).
        with _tmpdir() as d:
            d = Path(d)
            src = d / "node.md"
            src.write_text(self._NODE_TEMPLATE.format(task="nodeprobe"),
                           encoding="utf-8")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            self.assertEqual(values["test_command"],
                             "node --test ../tests/algo.test.mjs")
            self.assertNotIn("python", values["test_command"])

    def test_python_unittest_single_file_special_case(self):
        # (b) Contrato con el test_command actual del repo (runner python,
        # "python -m unittest tests/test_export_gate_contract.py"): es
        # EXACTAMENTE el caso especial documentado (4 tokens, archivo .py).
        # El export lo reescribe a invocacion directa "python <rel>" SIN
        # "-m unittest" — los archivos de test Python de este repo son
        # auto-ejecutables y "-m unittest" no acepta rutas con "..". El
        # caso Python SIGUE ejecutandose por el gate (regresión). out_dir =
        # raiz del repo (default real) -> sin ".." en target/tests; target
        # en scripts/, tests en tests/ -> rel "../tests/test_export_gate_contract.py".
        with _tmpdir() as d:
            d = Path(d)
            src = d / "pyrepo.md"
            src.write_text(self._PY_REPO_TEMPLATE.format(task="pyprobe"),
                           encoding="utf-8")
            out = egc.export_gate_contract(str(src), str(ROOT),
                                           repo_root=str(ROOT))
            self.addCleanup(lambda p=Path(out): p.unlink(missing_ok=True))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            self.assertEqual(values["test_command"],
                             "python "
                             "../tests/test_export_gate_contract.py")
            self.assertNotIn("-m unittest", values["test_command"])

    _PY_DISCOVER_TEMPLATE = """---
type: 'Task Contract'
title: 'Test python discover'
task: {task}
intent: "probar discover preserve runner"
target: src/users.py
signature: "def f(x):"
test_command: "python -m unittest discover -s tests"
budget:
  max_cyclomatic_complexity: 10
tests: "tests/test_users.py"
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: {task}

## Intent
- runner discover preservado (5 tokens, no caso especial)
"""

    _PY_DOTTED_TEMPLATE = """---
type: 'Task Contract'
title: 'Test python dotted module'
task: {task}
intent: "probar modulo dotted preserve runner"
target: src/users.py
signature: "def f(x):"
test_command: "python -m unittest tests.test_users"
budget:
  max_cyclomatic_complexity: 10
tests: "tests/test_users.py"
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: {task}

## Intent
- modulo dotted preservado (4 tokens, sin .py -> no caso especial)
"""

    def test_python_unittest_discover_preserves_runner(self):
        # test_command con MAS de 4 tokens ("python -m unittest discover -s
        # tests", 5 tokens) NO cae en el caso especial: el runner
        # "python -m unittest" se preserva literal (la ruta de tests no es
        # substring del comando, asi que se preserva tal cual).
        with _tmpdir() as d:
            d = Path(d)
            src = d / "disc.md"
            src.write_text(self._PY_DISCOVER_TEMPLATE.format(task="discprobe"),
                           encoding="utf-8")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            self.assertEqual(values["test_command"],
                             "python -m unittest discover -s tests")
            self.assertIn("python -m unittest", values["test_command"])

    def test_python_dotted_module_preserves_runner(self):
        # test_command de 4 tokens pero el 4to NO termina en ".py" (nombre
        # de modulo dotted "tests.test_users"): NO cae en el caso especial.
        # La ruta de tests ("tests/test_users.py") no es substring del
        # comando, asi que se preserva literal tal cual.
        with _tmpdir() as d:
            d = Path(d)
            src = d / "dot.md"
            src.write_text(self._PY_DOTTED_TEMPLATE.format(task="dotprobe"),
                           encoding="utf-8")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            content = Path(out).read_text(encoding="utf-8")
            values, _ = _fm_values(content)
            self.assertEqual(values["test_command"],
                             "python -m unittest tests.test_users")
            self.assertIn("python -m unittest", values["test_command"])

    def test_no_test_command_key_not_added(self):
        # Invariante explicita del contrato: si el contrato NO declara
        # test_command, el export NO agrega la clave (comportamiento
        # invariante respecto al estado anterior del codigo).
        with _tmpdir() as d:
            d = Path(d)
            src = d / "notc.md"
            src.write_text(
                "---\n"
                "type: 'Task Contract'\n"
                "task: notc\n"
                "intent: \"sin test_command\"\n"
                "target: src/users.py\n"
                "signature: \"def f(x):\"\n"
                "budget:\n"
                "  max_cyclomatic_complexity: 10\n"
                "tests: \"tests/test_users.py\"\n"
                "deps_allowed: []\n"
                "forbids: ['network', 'subprocess']\n"
                "---\n\n# Contract: notc\n",
                encoding="utf-8")
            out = egc.export_gate_contract(str(src), str(d / "out"))
            content = Path(out).read_text(encoding="utf-8")
            values, keys = _fm_values(content)
            self.assertNotIn("test_command", keys)
            self.assertNotIn("test_command", values)


class TestRealContractExport(unittest.TestCase):
    # Skip-guards (acoplamiento autorizado por C06): estos tests exportan el
    # contrato real validate-user-record.md (artefacto de ejemplo del
    # manifiesto); post-init se elimina -> se saltean limpio. En la plantilla
    # integra (fixture presente) siguen corriendo.
    @unittest.skipUnless(
        (ROOT / "knowledge" / "contracts" / "validate-user-record.md").is_file(),
        "ejemplo removido por init: knowledge/contracts/validate-user-record.md")
    def test_validate_user_record_export_ascii_and_paths_resolve(self):
        real = ROOT / "knowledge" / "contracts" / "validate-user-record.md"
        self.assertTrue(real.is_file(), "fixture faltante: {}".format(real))
        with _tmpdir() as d:
            out_dir = Path(d) / "gate-exports"
            out = egc.export_gate_contract(str(real), str(out_dir),
                                           repo_root=str(ROOT))
            content = Path(out).read_text(encoding="ascii")
            # 100% ASCII
            self.assertTrue(all(ord(c) < 128 for c in content))
            # target/tests reescritos resuelven a archivos existentes
            values, _ = _fm_values(content)
            export_dir = Path(out).resolve().parent
            target_resolved = (export_dir / values["target"]).resolve()
            tests_resolved = (export_dir / values["tests"]).resolve()
            self.assertTrue(target_resolved.is_file(),
                            "target no resuelve a archivo: {}".format(target_resolved))
            self.assertTrue(tests_resolved.is_file(),
                            "tests no resuelven a archivo: {}".format(tests_resolved))

    @unittest.skipUnless(
        (ROOT / "knowledge" / "contracts" / "validate-user-record.md").is_file(),
        "ejemplo removido por init: knowledge/contracts/validate-user-record.md")
    def test_real_contract_test_command_rewritten_and_runs_from_src(self):
        # Export del contrato real de C04 con out_dir = raiz del repo (el
        # default real): test_command se reescribe aplicando el caso
        # especial documentado ("python -m unittest <archivo>.py" -> "python
        # <archivo>.py", invocacion directa, SIN "-m unittest") y
        # reescribiendo la ruta -> "python ../tests/test_users.py" (cwd del
        # gate = dir del target = src/). El comando reescrito DEBE funcionar
        # corrido con subprocess desde src/ (exit 0): los archivos de test
        # Python de este repo son auto-ejecutables.
        real = ROOT / "knowledge" / "contracts" / "validate-user-record.md"
        self.assertTrue(real.is_file(), "fixture faltante: {}".format(real))
        out = egc.export_gate_contract(str(real), str(ROOT),
                                      repo_root=str(ROOT))
        self.addCleanup(lambda p=Path(out): p.unlink(missing_ok=True))
        content = Path(out).read_text(encoding="ascii")
        values, _ = _fm_values(content)
        self.assertEqual(values["test_command"],
                         "python ../tests/test_users.py")
        self.assertNotIn("-m unittest", values["test_command"])
        # El gate corre test_command con cwd = dir del target (src/). Lo
        # reproducimos: shell=False, lista de tokens, cwd = ROOT/src.
        cmd = values["test_command"].split()
        r = subprocess.run(cmd, cwd=str(ROOT / "src"),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         "test_command fallo desde src/:\n{}".format(r.stderr))


class TestCrossDrive(unittest.TestCase):
    # T10 (CONTRACT-08): el export reescribe rutas con os.path.relpath entre
    # repo_root y out_dir; un relpath entre C: y D: no existe en Windows
    # (ValueError "path is on mount ..."). Antes de reescribir, el export compara
    # unidades via ntpath.splitdrive y falla como I/O (exit 1), no como contrato
    # invalido (exit 2). El chequeo vive en una funcion PURA
    # (cross_drive_io_error) testeable con paths literales estilo Windows, de
    # modo que el caso cross-drive corra tambien en el CI Linux (ntpath parsea
    # letras de unidad sin importar el SO; en POSIX los paths reales no tienen
    # unidad -> splitdrive da '' -> no-op).

    def test_pure_diff_drives_error_names_both(self):
        # Paths literales Windows: distintas unidades -> error que nombra ambas.
        msg = egc.cross_drive_io_error(r"C:\repo\kdd", r"D:\out\exports")
        self.assertIsNotNone(msg)
        self.assertIn("C:", msg)
        self.assertIn("D:", msg)
        self.assertIn("no pueden cruzar unidades", msg)

    def test_pure_same_drive_ok(self):
        # Misma letra (distinto path) -> None (no error).
        self.assertIsNone(
            egc.cross_drive_io_error(r"C:\repo\kdd", r"C:\out\exports"))
        # Case-insensitive: 'C:' vs 'c:' es la misma unidad.
        self.assertIsNone(
            egc.cross_drive_io_error(r"C:\repo", r"c:\out"))

    def test_pure_posix_noop(self):
        # Paths POSIX reales: splitdrive da '' para ambos -> no-op (el chequeo
        # no dispara falsos positivos en Linux/Mac).
        self.assertIsNone(
            egc.cross_drive_io_error("/home/user/repo", "/tmp/out"))
        self.assertIsNone(
            egc.cross_drive_io_error("/var/repo", "/var/out"))

    def test_pure_unc_treated_as_drive(self):
        # UNC //host/share actua como unidad en ntpath; dos shares distintos ->
        # error (comportamiento coherente: no hay relpath entre shares).
        msg = egc.cross_drive_io_error(
            r"\\host1\share\repo", r"\\host2\share\out")
        self.assertIsNotNone(msg)

    @unittest.skipUnless(
        sys.platform.startswith("win"),
        "cross-drive solo aplica en Windows (POSIX no tiene unidades)")
    def test_cli_cross_drive_exit1_io_not_contract_invalid(self):
        # En un host Windows: repo-root y out-dir en unidades distintas -> el
        # chequeo dispara antes de reescribir/escribir y el CLI lo mapea a
        # exit 1 (I/O), NO a exit 2 (contrato invalido). El mensaje nombra
        # ambas unidades y explica la limitacion.
        #
        # El out-dir se elige en una unidad DISTINTA a la del repo (ROOT), que
        # NO necesita existir fisicamente: el error se lanza antes de cualquier
        # escritura (ntpath.splitdrive parsea la letra sin importar si la
        # unidad esta montada). Esto hace el test robusto al entorno: corre
        # igual venga el repo en D: (host real) o en C: (la copia temporal del
        # test de init, que vive bajo TEMP y arrastra el discover de la copia).
        import ntpath as _nt
        root_drive = _nt.splitdrive(str(ROOT))[0] or "C:"
        other = "D:" if root_drive.upper() != "D:" else "C:"
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "xdcli")
            r = subprocess.run(
                [sys.executable, str(SCRIPT), str(src),
                 "--out-dir", other + r"\nonexistent\cross\drive",
                 "--repo-root", str(ROOT)],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertNotIn("contrato invalido", r.stderr)
            self.assertIn("no pueden cruzar unidades", r.stderr)
            # el mensaje nombra ambas unidades (la del repo y la del out-dir)
            self.assertIn(root_drive, r.stderr)
            self.assertIn(other, r.stderr)


class TestCLIExitCodes(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True)

    def test_exit0_valid_contract(self):
        with _tmpdir() as d:
            d = Path(d)
            src = _write_contract(d, "cli0")
            r = self._run(str(src), "--out-dir", str(d / "out"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.strip())
            self.assertTrue(Path(r.stdout.strip()).is_file())

    def test_exit2_missing_frontmatter(self):
        with _tmpdir() as d:
            d = Path(d)
            src = d / "nofm.md"
            src.write_text("# Sin frontmatter\n\n- nada\n", encoding="utf-8")
            r = self._run(str(src), "--out-dir", str(d / "out"))
            self.assertEqual(r.returncode, 2, r.stderr)

    def test_exit2_missing_required_key(self):
        with _tmpdir() as d:
            d = Path(d)
            src = d / "nokeys.md"
            src.write_text(
                "---\ntype: 'Task Contract'\ntask: nope\n---\n\n# Body\n",
                encoding="utf-8")
            r = self._run(str(src), "--out-dir", str(d / "out"))
            self.assertEqual(r.returncode, 2, r.stderr)

    def test_exit1_io_missing_contract(self):
        with _tmpdir() as d:
            r = self._run(str(Path(d) / "noexiste.md"),
                          "--out-dir", str(Path(d) / "out"))
            self.assertEqual(r.returncode, 1, r.stderr)


if __name__ == "__main__":
    unittest.main()