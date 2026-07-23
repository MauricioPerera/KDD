"""Oraculo congelado del gate de rule contracts (Contrato 18).

Autorado por el orquestador ANTES de la delegacion. El implementador de
scripts/validate_rules.py NO escribe ni modifica este archivo. Formato de la
vertiente: knowledge/rule-contract-spec.md.

Contrato del gate:
    validate_rules(rules_dir: str) -> list
findings [{'file','level','rule','msg'}] ordenados (archivo, regla); vacia si
todo es conforme. Escanea SOLO *.rules.json. Directorio ausente o sin
*.rules.json -> lista vacia (capa opcional); el CLI imprime INFO y exit 0.
CLI espejo de validate_okf.py: exit 0 sin ERRORs, 1 con >=1 ERROR.

Reglas del gate (nombres congelados):
- JSON:           rule-set no parseable.
- FAMILIA:        clave top-level desconocida (validas: _comment, required, type,
                  enums, bounds, matches, refs, keyed_bounds, keyed_enums, each,
                  code_only, golden).
- GOLDEN:         clave golden ausente / sin path/sha256 / archivo inexistente /
                  golden no parseable.
- GOLDEN_FROZEN:  sha256 (LF-normalizado, mismo algoritmo que tests_sha256) no
                  coincide -> msg con hash esperado y actual.
- GOLDEN_FORMA:   golden sin refs dict o cases lista no vacia, o un caso sin
                  name/record dict/violations lista, o code_only_miss no subconjunto
                  de violations.
- CODE_ONLY:      entrada de code_only sin reason no vacia.
- REPRO:          rule_engine.evaluate sobre un caso no reproduce
                  set(violations) - set(code_only_miss) a nivel de campo top-level
                  -> msg que nombra el caso.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from validate_rules import validate_rules


def _seal(path):
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


GOLDEN_OK = {
    "refs": {"t": {"A": {"cap": 10, "codes": ["X", "Y"]}}},
    "cases": [
        {"name": "valido", "record": {"a": 1, "k": "A", "amt": 5, "code": "X"},
         "violations": [], "code_only_miss": []},
        {"name": "falta a", "record": {"k": "A", "amt": 5, "code": "X"},
         "violations": ["a"], "code_only_miss": []},
        {"name": "cap excedido", "record": {"a": 1, "k": "A", "amt": 11, "code": "X"},
         "violations": ["amt"], "code_only_miss": []},
        {"name": "frontera code_only", "record": {"a": 1, "k": "A", "amt": 5, "code": "X", "co": "raro"},
         "violations": ["co"], "code_only_miss": ["co"]},
    ],
}

RULESET_OK = {
    "required": [{"field": "a"}],
    "keyed_bounds": [{"field": "amt", "key": "k", "table": "t", "max_path": "cap"}],
    "keyed_enums": [{"field": "code", "key": "k", "table": "t", "values_path": "codes"}],
    "code_only": [{"rule": "co-especial", "field": "co",
                   "reason": "co exige logica no uniforme; se valida en codigo"}],
}


def _write_pair(d, ruleset=None, golden=None, seal=True, name="demo"):
    """Escribe golden + rule-set (con clave golden sellada) en d. Devuelve rutas."""
    ruleset = dict(RULESET_OK if ruleset is None else ruleset)
    golden = GOLDEN_OK if golden is None else golden
    gpath = os.path.join(d, name + "-golden.json")
    with open(gpath, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(golden, fh, indent=1)
        fh.write("\n")
    ruleset["golden"] = {"path": os.path.basename(gpath),
                         "sha256": _seal(gpath) if seal else "0" * 64}
    rpath = os.path.join(d, name + ".rules.json")
    with open(rpath, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(ruleset, fh, indent=1)
        fh.write("\n")
    return rpath, gpath


def _rules(findings):
    return {f["rule"] for f in findings if f["level"] == "ERROR"}


class TestValido(unittest.TestCase):
    def test_par_valido_sin_findings(self):
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d)
            findings = validate_rules(d)
            self.assertEqual(findings, [], msg=findings)


class TestCapaOpcional(unittest.TestCase):
    def test_dir_vacio(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(validate_rules(d), [])

    def test_dir_ausente(self):
        self.assertEqual(validate_rules(os.path.join("no", "existe", "xyz")), [])

    def test_ignora_json_que_no_es_rules(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "otro.json"), "w", encoding="utf-8") as fh:
                fh.write("{invalido")
            self.assertEqual(validate_rules(d), [])


class TestFamilias(unittest.TestCase):
    def test_familia_desconocida_es_error(self):
        rs = dict(RULESET_OK)
        rs["requird"] = [{"field": "a"}]  # typo
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, ruleset=rs)
            findings = validate_rules(d)
            self.assertIn("FAMILIA", _rules(findings))
            self.assertTrue(any("requird" in f["msg"] for f in findings), findings)

    def test_matches_es_familia_conocida(self):
        # Contrato 25: matches (propiedad de texto) es familia valida, top-level
        # y el par golden+rules con matches pasa completo (incluida REPRO).
        rs = {
            "required": [{"field": "name"}],
            "matches": [{"field": "name",
                         "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"}],
        }
        golden = {
            "refs": {},
            "cases": [
                {"name": "valido", "record": {"name": "mi-servidor"},
                 "violations": [], "code_only_miss": []},
                {"name": "no kebab", "record": {"name": "Mal_Nombre"},
                 "violations": ["name"], "code_only_miss": []},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, ruleset=rs, golden=golden)
            findings = validate_rules(d)
            self.assertEqual(findings, [], msg=findings)

    def test_matchess_typo_es_error(self):
        rs = dict(RULESET_OK)
        rs["matchess"] = [{"field": "a", "pattern": "^x$"}]  # typo
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, ruleset=rs)
            findings = validate_rules(d)
            self.assertIn("FAMILIA", _rules(findings))
            self.assertTrue(any("matchess" in f["msg"] for f in findings),
                            findings)


class TestGolden(unittest.TestCase):
    def test_sin_clave_golden(self):
        with tempfile.TemporaryDirectory() as d:
            rpath, _ = _write_pair(d)
            rs = json.load(open(rpath, encoding="utf-8"))
            del rs["golden"]
            json.dump(rs, open(rpath, "w", encoding="utf-8"))
            self.assertIn("GOLDEN", _rules(validate_rules(d)))

    def test_golden_inexistente(self):
        with tempfile.TemporaryDirectory() as d:
            rpath, gpath = _write_pair(d)
            os.unlink(gpath)
            self.assertIn("GOLDEN", _rules(validate_rules(d)))

    def test_sello_roto_nombra_ambos_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            rpath, gpath = _write_pair(d, seal=False)
            findings = validate_rules(d)
            self.assertIn("GOLDEN_FROZEN", _rules(findings))
            frozen = [f for f in findings if f["rule"] == "GOLDEN_FROZEN"][0]
            self.assertIn("0" * 64, frozen["msg"])
            self.assertIn(_seal(gpath), frozen["msg"])

    def test_golden_mal_formado(self):
        bad = {"refs": {}, "cases": [{"name": "x", "record": {},
                                      "violations": [], "code_only_miss": ["y"]}]}
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, golden=bad)
            self.assertIn("GOLDEN_FORMA", _rules(validate_rules(d)))


class TestCodeOnly(unittest.TestCase):
    def test_code_only_sin_razon(self):
        rs = dict(RULESET_OK)
        rs["code_only"] = [{"rule": "x", "field": "co"}]  # sin reason
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, ruleset=rs)
            self.assertIn("CODE_ONLY", _rules(validate_rules(d)))


class TestReproduccion(unittest.TestCase):
    def test_divergencia_motor_golden(self):
        # rule-set SIN la regla keyed_bounds -> el caso 'cap excedido' del golden
        # espera ['amt'] pero el motor no lo produce -> REPRO nombrando el caso.
        rs = {"required": [{"field": "a"}],
              "keyed_enums": RULESET_OK["keyed_enums"],
              "code_only": RULESET_OK["code_only"]}
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, ruleset=rs)
            findings = validate_rules(d)
            self.assertIn("REPRO", _rules(findings))
            repro = [f for f in findings if f["rule"] == "REPRO"][0]
            self.assertIn("cap excedido", repro["msg"])

    def test_code_only_miss_no_cuenta_como_divergencia(self):
        # El caso 'frontera code_only' del golden valido NO debe generar REPRO.
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d)
            self.assertEqual(validate_rules(d), [])


class TestDeterminismo(unittest.TestCase):
    def test_findings_ordenados_y_estables(self):
        rs = dict(RULESET_OK)
        rs["zzz"] = []
        rs["aaa"] = []
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, ruleset=rs)
            f1 = validate_rules(d)
            f2 = validate_rules(d)
            self.assertEqual(f1, f2)
            keys = [(f["file"], f["rule"]) for f in f1]
            self.assertEqual(keys, sorted(keys))


class TestRepoReal(unittest.TestCase):
    @unittest.skipUnless(
        os.path.isfile(os.path.join(ROOT, "examples", "rules",
                                    "payment-compliance.rules.json")),
        "ejemplo removido por init: examples/rules")
    def test_ejemplo_real_pasa_limpio(self):
        findings = validate_rules(os.path.join(ROOT, "examples", "rules"))
        errors = [f for f in findings if f["level"] == "ERROR"]
        self.assertEqual(errors, [], msg=errors)


class TestCLI(unittest.TestCase):
    def _run(self, path):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "validate_rules.py"), path],
            capture_output=True, text=True, encoding="utf-8")

    def test_exit_0_valido(self):
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d)
            r = self._run(d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # Reporte honesto: hubo archivos validados -> NO es el caso INFO
            # (capa opcional) y el resumen declara cuantos se revisaron.
            self.assertNotIn("INFO", r.stdout, r.stdout)
            self.assertIn("Resumen", r.stdout, r.stdout)
            self.assertIn("1 archivo", r.stdout, r.stdout)

    def test_exit_1_con_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write_pair(d, seal=False)
            r = self._run(d)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("GOLDEN_FROZEN", r.stdout)

    def test_exit_0_info_capa_opcional(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("INFO", r.stdout)
        r2 = self._run(os.path.join("no", "existe", "xyz"))
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("INFO", r2.stdout)


if __name__ == "__main__":
    unittest.main()
