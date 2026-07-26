"""Gate de cobertura de rule_hints: todo rule-id que un validador puede emitir
debe tener receta, y ninguna receta puede documentar un codigo que no existe.

Por que este test es el que importa: un mapa de hints sin gate envejece en
silencio. Alguien agrega un codigo nuevo a un validador, el agente lo recibe sin
receta y vuelve a iterar a ciegas -- exactamente el problema que el mapa venia a
resolver. La direccion inversa importa igual: un hint hacia un codigo inexistente
es documentacion de una regla que no existe, y manda al lector a buscar algo que
nunca va a ver.
"""
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, 'scripts')
sys.path.insert(0, SCRIPTS_DIR)

from rule_hints import HINTS, FALLBACK_HINT, hint_for, enrich  # noqa: E402

# Un rule-id aparece de DOS formas en los validadores, y hay que cubrir las dos:
#   (a) como literal, cuando se construye un finding: _finding(f, 'FM_KEY', ...)
#   (b) embebido en el texto que se imprime: print("ERROR [CONFIG_MISSING]: ...")
# Mirar solo (a) dejaba fuera los 3 codigos de validate_commit_message, que emite
# por la via (b) -- un falso negativo que habria dejado esos codigos sin cobertura
# garantizada justamente en el test que existe para garantizarla.
# Ademas, un rule-id no siempre lleva guion bajo: validate_okf emite INDEX, LINK,
# ORPHAN, TAGS y TYPE. Exigir el guion bajo dejaba 8 codigos reales fuera de la
# cobertura -- el agujero que este mismo gate destapo al probarlo end-to-end.
# El patron es una alternancia: CON guion bajo (FM_KEY, TASK_SCORE_MISMATCH) o una
# sola palabra de 3+ caracteres (INDEX, TAGS). Un solo patron no cubre ambas.
_CODE = r"""[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+|[A-Z][A-Z0-9]{2,}"""
_CODE_LITERAL_RE = re.compile(r"""['"](""" + _CODE + r""")['"]""")
_CODE_INLINE_RE = re.compile(r"""\[(""" + _CODE + r""")\]""")

# Literales en mayusculas que NO son rule-ids. Cada exclusion esta justificada:
# ampliar esta lista para callar el gate seria vaciarlo de sentido.
_NOT_RULE_IDS = {
    # entorno / encoding
    'UTF_8', 'NO_COLOR', 'PYTHONIOENCODING', 'LC_ALL', 'PATH_MAX',
    # niveles de severidad de un finding, no codigos
    # (ojo: 'JSON' NO va aca -- validate_rules lo emite como rule-id real)
    'ERROR', 'WARNING', 'INFO', 'PASS', 'FAIL', 'SKIP',
    # nombres de familia del rule-engine y claves permitidas de un rule-set:
    # aparecen como literales pero se emiten con sufijo (GOLDEN_FORMA, GOLDEN_FROZEN)
    'GOLDEN',
}

# Scripts que emiten hallazgos. El resto (assemble_context, init_project,
# export_gate_contract, mcp_*, benchmark, preflight) orquestan o exportan.
_EMITTERS = (
    'audit_forbids.py',
    'audit_seals.py', 'scan_secrets.py', 'validate_attestation.py',
    'validate_changelog.py', 'validate_commit_message.py', 'validate_contracts.py',
    'validate_diagrams.py', 'validate_okf.py', 'validate_perimeter.py',
    'validate_rules.py', 'validate_skills.py', 'validate_specs.py',
    'validate_ux_page.py',
)


def _emitted_codes():
    """Rule-ids que los validadores pueden emitir, extraidos del fuente."""
    found = {}
    for name in _EMITTERS:
        path = os.path.join(SCRIPTS_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        for regex in (_CODE_LITERAL_RE, _CODE_INLINE_RE):
            for code in regex.findall(text):
                if code not in _NOT_RULE_IDS:
                    found.setdefault(code, set()).add(name)
    return found


class TestRuleHintsCoverage(unittest.TestCase):

    def test_every_emitted_code_has_a_hint(self):
        emitted = _emitted_codes()
        self.assertTrue(emitted, 'no se extrajo ningun rule-id: el extractor esta roto')
        missing = sorted(c for c in emitted if c not in HINTS)
        self.assertEqual(
            missing, [],
            'rule-ids sin receta en scripts/rule_hints.py: {}. Agregalos (los emite: {}).'.format(
                ', '.join(missing),
                '; '.join('{} -> {}'.format(c, ','.join(sorted(emitted[c]))) for c in missing)))

    def test_no_hint_documents_a_nonexistent_code(self):
        emitted = _emitted_codes()
        orphans = sorted(c for c in HINTS if c not in emitted)
        self.assertEqual(
            orphans, [],
            'recetas para rule-ids que ningun validador emite: {}. '
            'Borralas o corrige el codigo.'.format(', '.join(orphans)))

    def test_hints_are_actionable(self):
        """Una receta dice QUE HACER: ni vacia, ni el fallback disfrazado.

        No se comprueba que el hint evite mencionar su propio codigo: varios
        codigos SON el nombre del artefacto que hay que escribir ('ABORTAR SI',
        'TOCAR_SOLO', 'CODE_ONLY'), y nombrarlo es justamente lo accionable.
        """
        for code, hint in sorted(HINTS.items()):
            self.assertIsInstance(hint, str, code)
            self.assertGreaterEqual(
                len(hint), 40,
                '{}: la receta es demasiado corta para ser accionable'.format(code))
            self.assertNotEqual(
                hint.strip(), FALLBACK_HINT.strip(),
                '{}: rellenar con el fallback calla el gate sin aportar receta'.format(code))

    def test_hint_for_falls_back_instead_of_failing(self):
        self.assertEqual(hint_for('CODIGO_QUE_NO_EXISTE'), FALLBACK_HINT)
        self.assertEqual(hint_for('FM_TESTS_FROZEN'), HINTS['FM_TESTS_FROZEN'])

    def test_enrich_adds_hint_without_mutating_input(self):
        findings = [{'file': 'a.md', 'level': 'ERROR', 'rule': 'FM_KEY', 'msg': 'x'}]
        out = enrich(findings)
        self.assertEqual(out[0]['hint'], HINTS['FM_KEY'])
        self.assertNotIn('hint', findings[0], 'enrich no debe mutar la entrada')
        self.assertEqual(out[0]['rule'], 'FM_KEY')

    def test_enrich_uses_fallback_for_unknown_rule(self):
        out = enrich([{'file': 'a', 'level': 'ERROR', 'rule': 'NOPE_NOPE', 'msg': 'x'}])
        self.assertEqual(out[0]['hint'], FALLBACK_HINT)


if __name__ == '__main__':
    unittest.main()
