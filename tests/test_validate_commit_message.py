"""Oraculo congelado del gate de formato de mensaje de commit (Contrato 31).

Calibrado contra Conventional Commits v1.0.0 (https://www.conventionalcommits.org/)
y las reglas por defecto de commitlint — no reglas inventadas. Herramienta OPT-IN:
NO es gate de CI de este repo (el propio historial de KDD no sigue esta convencion).

  Gramatica del header (linea 1): ``tipo(scope)?!?: descripcion``
  - ``tipo``: palabra sin espacios (letras/numeros/guiones).
  - ``(scope)``: opcional, entre parentesis, sin parentesis anidados.
  - ``!``: opcional, marca breaking change (no se valida su veracidad: eso exige el
    diff real, fuera de alcance de un checker de solo-texto).
  - ``: `` (dos puntos + un espacio) seguido de la descripcion (resto de la linea,
    no vacia).

  ``parse_commit_message(msg) -> dict | None``
    Devuelve ``{'type','scope','breaking','description','header','body'}`` si el
    header matchea la gramatica (``scope`` es ``None`` si no hay parentesis; ``body``
    es el texto desde la linea 3 en adelante, o ``''`` si no hay; ``header`` es la
    linea 1 tal cual). Devuelve ``None`` si el header NO matchea la gramatica en
    absoluto (sin ':' , tipo vacio, etc.) — msg vacio o solo whitespace tambien ``None``.

  ``check_commit_message(msg, config) -> list``
    findings ``{'level','rule','msg'}`` (SIN 'file': un mensaje de commit no es un
    archivo del repo). ``config``: ``{'types': [...], 'scope_required': bool,
    'max_subject_length': int}``.

    Reglas y severidad EXACTA:
      HEADER_MALFORMED (ERROR)      parse_commit_message devuelve None. Las demas
                                    reglas se omiten (no hay estructura que revisar).
      TYPE_UNKNOWN (ERROR)          el 'type' parseado no esta en config['types'].
      SCOPE_REQUIRED (ERROR)        config['scope_required'] es True y 'scope' es None.
      BLANK_LINE_MISSING (ERROR)    hay una linea 3 (o mas) no vacia (cuerpo real) Y
                                    la linea 2 NO esta vacia/blanca.
      SUBJECT_TOO_LONG (WARNING)    len(header) > config['max_subject_length'].
      SUBJECT_TRAILING_PERIOD (WARNING) la 'description' termina en '.'.

  ``main(argv) -> int``
    ``argv[0]`` es el path a un JSON de config. El mensaje viene de UNA de estas
    fuentes (mutuamente excluyentes, en este orden de precedencia si varias se
    pasan): ``--message <texto>``, ``--file <path>``, o si ninguna de las dos
    aparece, se lee de stdin. Imprime cada finding y termina con
    ``Resumen: N error(es), M warning(s)``. Exit 1 si hay >=1 ERROR (incluido un
    config JSON invalido o inexistente -> ERROR "CONFIG_INVALID"/"CONFIG_MISSING",
    exit 1), si no exit 0. WARNING nunca bloquea.

Este archivo es un ORACULO CONGELADO (tests_sha256): el implementador no lo
modifica. Ver knowledge/contracts/commit-message-gate.md.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import validate_commit_message as vcm  # noqa: E402


CONFIG = {
    "types": ["feat", "fix", "docs", "refactor", "test", "chore"],
    "scope_required": False,
    "max_subject_length": 72,
}


class TestParse(unittest.TestCase):
    def test_header_simple(self):
        r = vcm.parse_commit_message("feat: agrega X")
        self.assertEqual(r["type"], "feat")
        self.assertIsNone(r["scope"])
        self.assertFalse(r["breaking"])
        self.assertEqual(r["description"], "agrega X")
        self.assertEqual(r["header"], "feat: agrega X")
        self.assertEqual(r["body"], "")

    def test_header_con_scope(self):
        r = vcm.parse_commit_message("fix(parser): corrige Y")
        self.assertEqual(r["type"], "fix")
        self.assertEqual(r["scope"], "parser")
        self.assertEqual(r["description"], "corrige Y")

    def test_breaking_con_bang(self):
        r = vcm.parse_commit_message("feat(api)!: cambia Z")
        self.assertTrue(r["breaking"])
        self.assertEqual(r["scope"], "api")

    def test_con_cuerpo(self):
        msg = "feat: agrega X\n\nEsto explica por que.\nSegunda linea."
        r = vcm.parse_commit_message(msg)
        self.assertEqual(r["body"], "Esto explica por que.\nSegunda linea.")

    def test_sin_dos_puntos_es_none(self):
        self.assertIsNone(vcm.parse_commit_message("agrega X sin formato"))

    def test_tipo_vacio_es_none(self):
        self.assertIsNone(vcm.parse_commit_message(": agrega X"))

    def test_descripcion_vacia_es_none(self):
        self.assertIsNone(vcm.parse_commit_message("feat: "))

    def test_mensaje_vacio_es_none(self):
        self.assertIsNone(vcm.parse_commit_message(""))
        self.assertIsNone(vcm.parse_commit_message("   \n  "))


class TestCheck(unittest.TestCase):
    def _rules(self, findings, level=None):
        if level is None:
            return sorted(f["rule"] for f in findings)
        return sorted(f["rule"] for f in findings if f["level"] == level)

    def test_mensaje_valido_sin_findings(self):
        findings = vcm.check_commit_message("feat(gate): agrega validador", CONFIG)
        self.assertEqual(findings, [])

    def test_header_malformado(self):
        findings = vcm.check_commit_message("sin formato de commit", CONFIG)
        self.assertEqual(self._rules(findings), ["HEADER_MALFORMED"])
        self.assertEqual(findings[0]["level"], "ERROR")

    def test_header_malformado_omite_las_demas_reglas(self):
        # Un mensaje malformado no debe ademas disparar TYPE_UNKNOWN u otras --
        # no hay estructura parseada sobre la cual evaluarlas.
        findings = vcm.check_commit_message("x", CONFIG)
        self.assertEqual(len(findings), 1)

    def test_tipo_desconocido(self):
        findings = vcm.check_commit_message("banana: algo raro", CONFIG)
        self.assertEqual(self._rules(findings), ["TYPE_UNKNOWN"])
        self.assertEqual(findings[0]["level"], "ERROR")

    def test_scope_requerido_y_ausente(self):
        cfg = dict(CONFIG, scope_required=True)
        findings = vcm.check_commit_message("feat: agrega X", cfg)
        self.assertEqual(self._rules(findings), ["SCOPE_REQUIRED"])

    def test_scope_requerido_y_presente(self):
        cfg = dict(CONFIG, scope_required=True)
        findings = vcm.check_commit_message("feat(x): agrega X", cfg)
        self.assertEqual(findings, [])

    def test_linea_en_blanco_faltante_antes_del_cuerpo(self):
        msg = "feat: agrega X\nEsto no deberia estar aca sin blank line"
        findings = vcm.check_commit_message(msg, CONFIG)
        self.assertEqual(self._rules(findings), ["BLANK_LINE_MISSING"])
        self.assertEqual(findings[0]["level"], "ERROR")

    def test_linea_en_blanco_presente_ok(self):
        msg = "feat: agrega X\n\nCuerpo correctamente separado."
        self.assertEqual(vcm.check_commit_message(msg, CONFIG), [])

    def test_subject_muy_largo(self):
        header = "feat: " + ("x" * 80)
        findings = vcm.check_commit_message(header, CONFIG)
        self.assertEqual(self._rules(findings), ["SUBJECT_TOO_LONG"])
        self.assertEqual(findings[0]["level"], "WARNING")

    def test_subject_termina_en_punto(self):
        findings = vcm.check_commit_message("feat: agrega X.", CONFIG)
        self.assertEqual(self._rules(findings), ["SUBJECT_TRAILING_PERIOD"])
        self.assertEqual(findings[0]["level"], "WARNING")

    def test_solo_warnings_no_impide_lista_vacia_de_errores(self):
        header = "feat: " + ("x" * 80) + "."
        findings = vcm.check_commit_message(header, CONFIG)
        errors = [f for f in findings if f["level"] == "ERROR"]
        warnings = [f for f in findings if f["level"] == "WARNING"]
        self.assertEqual(errors, [])
        self.assertEqual(
            sorted(w["rule"] for w in warnings),
            ["SUBJECT_TOO_LONG", "SUBJECT_TRAILING_PERIOD"],
        )

    def test_determinismo(self):
        msg = "fix(x): repara Y"
        self.assertEqual(
            vcm.check_commit_message(msg, CONFIG),
            vcm.check_commit_message(msg, CONFIG),
        )


class TestCli(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="c31_")
        self.addCleanup(__import__("shutil").rmtree, self.base, ignore_errors=True)
        self.cfg_path = os.path.join(self.base, "config.json")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(CONFIG, fh)

    def test_message_flag_valido_exit_0(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([self.cfg_path, "--message", "feat: agrega X"])
        self.assertEqual(code, 0)
        self.assertIn("0 error(es)", out.getvalue())

    def test_message_flag_invalido_exit_1(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([self.cfg_path, "--message", "banana: algo"])
        self.assertEqual(code, 1)
        self.assertIn("TYPE_UNKNOWN", out.getvalue())

    def test_solo_warning_exit_0(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([self.cfg_path, "--message", "feat: agrega X."])
        self.assertEqual(code, 0)
        self.assertIn("SUBJECT_TRAILING_PERIOD", out.getvalue())
        self.assertIn("1 warning(s)", out.getvalue())

    def test_file_flag(self):
        msg_path = os.path.join(self.base, "msg.txt")
        with open(msg_path, "w", encoding="utf-8") as fh:
            fh.write("docs: actualiza README")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([self.cfg_path, "--file", msg_path])
        self.assertEqual(code, 0)

    def test_stdin(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("chore: tarea de mantenimiento")
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = vcm.main([self.cfg_path])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)

    def test_config_inexistente_exit_1(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([
                os.path.join(self.base, "no-existe.json"),
                "--message", "feat: x",
            ])
        self.assertEqual(code, 1)
        self.assertIn("CONFIG_MISSING", out.getvalue())

    def test_config_json_invalido_exit_1(self):
        bad = os.path.join(self.base, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([bad, "--message", "feat: x"])
        self.assertEqual(code, 1)
        self.assertIn("CONFIG_INVALID", out.getvalue())

    def test_config_sin_claves_requeridas_exit_1(self):
        # H-2: config JSON valido como objeto pero sin 'types' ni
        # 'max_subject_length' (claves que check_commit_message indexa directo).
        # Antes del fix esto crasheaba con KeyError (traceback). Ahora debe ser
        # finding CONFIG_INVALID + exit 1, sin traceback.
        bad = os.path.join(self.base, "nokeys.json")
        with open(bad, "w", encoding="utf-8") as fh:
            json.dump({"scope_required": False}, fh)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([bad, "--message", "feat: x"])
        self.assertEqual(code, 1)
        self.assertIn("CONFIG_INVALID", out.getvalue())
        self.assertNotIn("Traceback", out.getvalue())

    def test_config_no_es_objeto_exit_1(self):
        # H-2: config JSON valido pero no es un objeto (array) -> antes del fix
        # crasheaba con TypeError/KeyError. Ahora CONFIG_INVALID + exit 1.
        bad = os.path.join(self.base, "array.json")
        with open(bad, "w", encoding="utf-8") as fh:
            json.dump(["types", "max_subject_length"], fh)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vcm.main([bad, "--message", "feat: x"])
        self.assertEqual(code, 1)
        self.assertIn("CONFIG_INVALID", out.getvalue())
        self.assertNotIn("Traceback", out.getvalue())


if __name__ == "__main__":
    unittest.main()
