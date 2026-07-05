"""Coherencia del dialecto YAML entre los dos parsers duplicados.

``scripts/validate_contracts.py`` y ``scripts/validate_okf.py`` duplican a
proposico el mismo parser YAML minimal (autocontenimiento de cada
validador). Este test fija que sigan siendo el MISMO dialecto: las mismas
fixtures de frontmatter, parseadas por ambos, deben producir outputs
identicos. No acopla los scripts (no los modifica): solo los importa y
compara. Si alguien edita un parser y olvida el otro, este test falla.

Fixtures: escalares (plain / single-quote / double-quote / vacio), listas
inline (vacia / de escalares / comillas con coma interna), dicts anidados
por indentacion, y casos borde del dialecto (mezcla de todo lo anterior).
"""

import os
import sys
import unittest

# hacer importables los modulos de scripts/ (no es paquete).
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import validate_contracts as vc  # noqa: E402
import validate_okf as vok  # noqa: E402


# Fixtures de frontmatter cubriendo el dialecto compartido.
# Clave -> texto crudo (con '---' delimitadores y cuerpo).
FIXTURES = {
    "scalars_plain": (
        "---\n"
        "type: Task Contract\n"
        "plain: hello world\n"
        "n: 42\n"
        "---\n\n# Body\n"
    ),
    "scalars_quoted": (
        "---\n"
        "type: 'Task Contract'\n"
        "title: \"Demo\"\n"
        "empty: ''\n"
        "empty_dq: \"\"\n"
        "---\n\n# Body\n"
    ),
    "inline_list_empty": (
        "---\n"
        "deps_allowed: []\n"
        "forbids: []\n"
        "---\n\n# Body\n"
    ),
    "inline_list_scalars": (
        "---\n"
        "forbids: ['network', 'subprocess']\n"
        "tags: [\"alpha\", 'beta']\n"
        "---\n\n# Body\n"
    ),
    "inline_list_comma_inside_quotes": (
        # 'b,c' es UN item: el split respeta comillas.
        "---\n"
        "tags: [\"a\", 'b,c']\n"
        "mix: ['x', \"y,z\", w]\n"
        "---\n\n# Body\n"
    ),
    "nested_dict": (
        "---\n"
        "budget:\n"
        "  max_cyclomatic_complexity: 10\n"
        "  max_nesting_depth: 4\n"
        "---\n\n# Body\n"
    ),
    "nested_dict_quoted_child": (
        "---\n"
        "budget:\n"
        "  a: 1\n"
        "  b: 'two'\n"
        "---\n\n# Body\n"
    ),
    "no_frontmatter": (
        "# Sin frontmatter\n\n- nada\n"
    ),
    "leading_blank_then_frontmatter": (
        "\n\n---\n"
        "task: t\n"
        "---\n\n# Body\n"
    ),
    "full_mix": (
        "---\n"
        "type: 'Task Contract'\n"
        "task: hello_world\n"
        "intent: \"Demostrar structura.\"\n"
        "target: src/hello.py\n"
        "test_command: \"python -m unittest tests/test_sample.py\"\n"
        "budget:\n"
        "  max_cyclomatic_complexity: 2\n"
        "  max_nesting_depth: 1\n"
        "tests: \"tests/test_sample.py\"\n"
        "deps_allowed: []\n"
        "forbids: ['network', 'subprocess']\n"
        "---\n\n# Contract: Hello World\n"
    ),
}


class TestParserCoherence(unittest.TestCase):
    """Ambos parsers deben devolver el mismo (dict, body) para cada fixture."""

    def test_identical_dict_and_body(self):
        for name, text in FIXTURES.items():
            with self.subTest(fixture=name):
                d_vc, b_vc = vc.parse_frontmatter(text)
                d_ok, b_ok = vok.parse_frontmatter(text)
                self.assertEqual(
                    d_vc, d_ok,
                    "dict difiere para {!r}:\n  vc={!r}\n  ok={!r}".format(
                        name, d_vc, d_ok))
                self.assertEqual(
                    b_vc, b_ok,
                    "body difiere para {!r}:\n  vc={!r}\n  ok={!r}".format(
                        name, b_vc, b_ok))

    def test_parsers_export_same_symbols(self):
        # El dialecto compartido se apoya en estas 4 funciones identicas.
        for fn in ("_split_inline_list", "_parse_scalar",
                   "_parse_block", "parse_frontmatter"):
            self.assertTrue(hasattr(vc, fn),
                           "validate_contracts sin {}".format(fn))
            self.assertTrue(hasattr(vok, fn),
                           "validate_okf sin {}".format(fn))


if __name__ == "__main__":
    unittest.main()