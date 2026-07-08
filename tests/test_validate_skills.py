"""Oraculo congelado del gate de skills (Contrato 24).

Fija el comportamiento de ``scripts/validate_skills.py``:

  API:  ``def validate_skills(skill_dirs) -> list`` donde ``skill_dirs`` es una
  lista de directorios. Cada SUBDIRECTORIO INMEDIATO de cada dir es una skill y
  debe contener ``SKILL.md``. Archivos sueltos en el dir (p. ej. un README.md)
  NO son skills y se ignoran. Devuelve findings ``{'file','level','rule','msg'}``
  ordenados por (file, rule). Rutas de finding en estilo posix ('/').

  Checks por skill (rule -> condicion de ERROR):
    SKILL_MISSING  subdirectorio sin SKILL.md (file = "<dir>/<skill>").
    FM_PARSE       sin frontmatter o frontmatter no parseable (mismo dialecto
                   mini-YAML que validate_contracts/validate_okf; tercera copia
                   fijada por test_parser_coherence a 3 vias). Si dispara, las
                   demas checks de ese archivo se omiten.
    FM_NAME        'name' ausente, no-string o vacio.
    FM_NAME_KEBAB  'name' no kebab-case (regex ^[a-z0-9]+(-[a-z0-9]+)*$).
    FM_NAME_DIR    'name' distinto del nombre del directorio.
    FM_DESC        'description' ausente, no-string o vacia.
    FM_DESC_LEN    largo de 'description' fuera de [50, 1024] (inclusive);
                   el msg incluye el largo real.
    BODY_EMPTY     cuerpo (tras el frontmatter) vacio al hacer strip().
    LINK_BROKEN    enlace markdown relativo del CUERPO que no resuelve a un
                   archivo o directorio existente (resuelto desde el dir del
                   SKILL.md; puede salir del dir de skills y resolver en el
                   repo). Se ignoran: enlaces externos (esquema '://', mailto:),
                   anclas puras ('#...'), y todo enlace dentro de code spans
                   (`...`) o bloques vallados (```...```) — mismo stripping que
                   validate_okf. El msg nombra el target roto.
    NAME_DUP       'name' repetido entre skills escaneadas (considerando TODOS
                   los dirs); un finding por ocurrencia extra, anclado en el
                   archivo lexicograficamente posterior; el msg incluye el name.

  Capa opcional: dir inexistente -> finding INFO (rule DIR_MISSING, file = el
  dir) y NO cuenta como error.

  CLI:  ``python scripts/validate_skills.py [dir ...]`` (default:
  ``skills .agents/skills``). ``main(argv) -> int``: imprime findings y un
  Resumen HONESTO: "Resumen: N error(es) en M skill(s)" donde M es la cantidad
  de skills ESCANEADAS (subdirectorios inmediatos examinados, tengan findings
  o no) — nunca derivada solo de los findings. exit 0 sin ERRORs (INFO no
  cuenta), 1 con >=1 ERROR.

Este archivo es un ORACULO CONGELADO (tests_sha256): el implementador no lo
modifica. Ver knowledge/contracts/skills-gate.md.
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import validate_skills as vs  # noqa: E402

DESC_OK = ("Descripcion de prueba con largo suficiente para superar la cota "
           "inferior de cincuenta caracteres del gate de skills.")
BODY_OK = "# Titulo\n\nCuerpo minimo de la skill.\n"


def _skill_text(name, description=DESC_OK, body=BODY_OK, extra_fm=""):
    return ("---\n"
            "name: {}\n"
            "description: {}\n"
            "{}"
            "---\n\n"
            "{}").format(name, description, extra_fm, body)


class _TmpDirs(unittest.TestCase):
    """Base: un tempdir raiz donde crear dirs de skills de fixture."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="c24_")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def _dir(self, rel):
        d = os.path.join(self.base, rel)
        os.makedirs(d, exist_ok=True)
        return d

    def _write_skill(self, dirs_rel, skill, text):
        d = os.path.join(self.base, dirs_rel, skill)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "SKILL.md")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    def _errors(self, findings):
        return [f for f in findings if f["level"] == "ERROR"]


class TestValidSkill(_TmpDirs):

    def test_valid_skill_no_findings(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill"))
        self.assertEqual(vs.validate_skills([d]), [])

    def test_top_level_files_ignored(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill"))
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("# no soy una skill\n")
        self.assertEqual(vs.validate_skills([d]), [])

    def test_finding_shape_and_order(self):
        d = self._dir("sk")
        # dos skills rotas -> findings ordenados por (file, rule)
        self._write_skill("sk", "b-skill", _skill_text("otro-nombre"))
        os.makedirs(os.path.join(d, "a-vacia"))
        findings = vs.validate_skills([d])
        self.assertTrue(findings)
        for f in findings:
            self.assertEqual(sorted(f.keys()),
                             ["file", "level", "msg", "rule"])
            self.assertNotIn("\\", f["file"])
        keys = [(f["file"], f["rule"]) for f in findings]
        self.assertEqual(keys, sorted(keys))


class TestSkillMd(_TmpDirs):

    def test_missing_skill_md(self):
        d = self._dir("sk")
        os.makedirs(os.path.join(d, "sin-archivo"))
        findings = vs.validate_skills([d])
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f["rule"], "SKILL_MISSING")
        self.assertEqual(f["level"], "ERROR")
        self.assertTrue(f["file"].endswith("sin-archivo"))

    def test_no_frontmatter_fm_parse_only(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill", "# Sin frontmatter\n\ncuerpo\n")
        findings = vs.validate_skills([d])
        self.assertEqual([f["rule"] for f in findings], ["FM_PARSE"])


class TestName(_TmpDirs):

    def test_name_missing(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill",
                          "---\ndescription: {}\n---\n\n{}".format(
                              DESC_OK, BODY_OK))
        rules = [f["rule"] for f in vs.validate_skills([d])]
        self.assertIn("FM_NAME", rules)

    def test_name_not_kebab(self):
        d = self._dir("sk")
        self._write_skill("sk", "Mi_Skill", _skill_text("Mi_Skill"))
        rules = [f["rule"] for f in vs.validate_skills([d])]
        self.assertIn("FM_NAME_KEBAB", rules)

    def test_name_dir_mismatch(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill", _skill_text("otra-cosa"))
        rules = [f["rule"] for f in vs.validate_skills([d])]
        self.assertIn("FM_NAME_DIR", rules)
        self.assertNotIn("FM_NAME_KEBAB", rules)


class TestDescription(_TmpDirs):

    def test_description_missing(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill",
                          "---\nname: mi-skill\n---\n\n{}".format(BODY_OK))
        rules = [f["rule"] for f in vs.validate_skills([d])]
        self.assertIn("FM_DESC", rules)

    def test_description_too_short(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill",
                          _skill_text("mi-skill", description="x" * 49))
        findings = [f for f in vs.validate_skills([d])
                    if f["rule"] == "FM_DESC_LEN"]
        self.assertEqual(len(findings), 1)
        self.assertIn("49", findings[0]["msg"])

    def test_description_bounds_inclusive(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill",
                          _skill_text("mi-skill", description="x" * 50))
        self._write_skill("sk", "mi-skill-b",
                          _skill_text("mi-skill-b", description="y" * 1024))
        self.assertEqual(vs.validate_skills([d]), [])

    def test_description_too_long(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill",
                          _skill_text("mi-skill", description="x" * 1025))
        findings = [f for f in vs.validate_skills([d])
                    if f["rule"] == "FM_DESC_LEN"]
        self.assertEqual(len(findings), 1)
        self.assertIn("1025", findings[0]["msg"])


class TestBodyAndLinks(_TmpDirs):

    def test_body_empty(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill", body="  \n"))
        rules = [f["rule"] for f in vs.validate_skills([d])]
        self.assertIn("BODY_EMPTY", rules)

    def test_broken_relative_link(self):
        d = self._dir("sk")
        body = "Ver [doc](../no-existe/SKILL.md) para mas.\n"
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill", body=body))
        findings = [f for f in vs.validate_skills([d])
                    if f["rule"] == "LINK_BROKEN"]
        self.assertEqual(len(findings), 1)
        self.assertIn("../no-existe/SKILL.md", findings[0]["msg"])

    def test_link_resolves_outside_skills_dir(self):
        d = self._dir("sk")
        shared = os.path.join(self.base, "docs")
        os.makedirs(shared)
        with open(os.path.join(shared, "guia.md"), "w", encoding="utf-8") as fh:
            fh.write("# guia\n")
        body = "Ver [guia](../../docs/guia.md).\n"
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill", body=body))
        self.assertEqual(vs.validate_skills([d]), [])

    def test_sibling_link_ok(self):
        d = self._dir("sk")
        self._write_skill("sk", "otra-skill", _skill_text("otra-skill"))
        body = "Hermana de [otra](../otra-skill/SKILL.md).\n"
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill", body=body))
        self.assertEqual(vs.validate_skills([d]), [])

    def test_external_and_anchor_links_ignored(self):
        d = self._dir("sk")
        body = ("Ver [repo](https://github.com/x/y/blob/main/SKILL.md), "
                "[mail](mailto:a@b.c) y [ancla](#seccion).\n")
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill", body=body))
        self.assertEqual(vs.validate_skills([d]), [])

    def test_links_in_code_span_and_fence_ignored(self):
        d = self._dir("sk")
        body = ("Ejemplo: `[doc](../nope/a.md)` inline.\n\n"
                "```\n[otro](../nope/b.md)\n```\n\nfin.\n")
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill", body=body))
        self.assertEqual(vs.validate_skills([d]), [])


class TestUniqueness(_TmpDirs):

    def test_duplicate_name_across_dirs(self):
        d1 = self._dir("sk1")
        d2 = self._dir("sk2")
        self._write_skill("sk1", "mi-skill", _skill_text("mi-skill"))
        self._write_skill("sk2", "mi-skill", _skill_text("mi-skill"))
        findings = vs.validate_skills([d1, d2])
        dups = [f for f in findings if f["rule"] == "NAME_DUP"]
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["level"], "ERROR")
        self.assertIn("mi-skill", dups[0]["msg"])
        # anclado en el archivo lexicograficamente posterior
        self.assertIn("sk2", dups[0]["file"])

    def test_distinct_names_ok(self):
        d1 = self._dir("sk1")
        d2 = self._dir("sk2")
        self._write_skill("sk1", "una-skill", _skill_text("una-skill"))
        self._write_skill("sk2", "otra-skill", _skill_text("otra-skill"))
        self.assertEqual(vs.validate_skills([d1, d2]), [])


class TestOptionalLayerAndCli(_TmpDirs):

    def test_missing_dir_is_info(self):
        missing = os.path.join(self.base, "no-existe")
        findings = vs.validate_skills([missing])
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f["level"], "INFO")
        self.assertEqual(f["rule"], "DIR_MISSING")

    def test_cli_exit_0_valid_and_missing(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill", _skill_text("mi-skill"))
        missing = os.path.join(self.base, "no-existe")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vs.main([d, missing])
        self.assertEqual(code, 0)
        self.assertIn("Resumen", out.getvalue())

    def test_cli_resumen_counts_scanned_skills(self):
        # 2 skills validas y limpias: el Resumen debe decir 2, no 0.
        d = self._dir("sk")
        self._write_skill("sk", "una-skill", _skill_text("una-skill"))
        self._write_skill("sk", "otra-skill", _skill_text("otra-skill"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vs.main([d])
        self.assertEqual(code, 0)
        self.assertIn("0 error(es) en 2 skill(s)", out.getvalue())

    def test_cli_exit_1_on_error(self):
        d = self._dir("sk")
        self._write_skill("sk", "mi-skill", _skill_text("rota"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vs.main([d])
        self.assertEqual(code, 1)
        self.assertIn("FM_NAME_DIR", out.getvalue())

    def test_determinism_two_runs(self):
        d = self._dir("sk")
        self._write_skill("sk", "b-skill", _skill_text("otro"))
        os.makedirs(os.path.join(d, "a-vacia"))
        self.assertEqual(vs.validate_skills([d]), vs.validate_skills([d]))


class TestRealAssets(unittest.TestCase):
    """El gate custodia activos REALES: las skills del repo pasan limpias."""

    def test_repo_skills_have_no_errors(self):
        dirs = [os.path.join(ROOT, "skills"),
                os.path.join(ROOT, ".agents", "skills")]
        findings = vs.validate_skills(dirs)
        errors = [f for f in findings if f["level"] == "ERROR"]
        self.assertEqual(errors, [], "activos reales con errores: {!r}".format(
            errors))


if __name__ == "__main__":
    unittest.main()
