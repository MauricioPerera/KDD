"""Tests unitarios del validador OKF (scripts/validate_okf.py).

Fixtures propias en tempdir (NO tocan la KB real) + un test contra la KB real
del repo (debe pasar limpia). Los tests del CLI usan subprocess (permitido en
tests, prohibido en el target).
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import validate_okf as vo  # noqa: E402


# ---------------------------------------------------------------------------
# Plantillas de fixture
# ---------------------------------------------------------------------------

INDEX_BODY = """# Knowledge Bundle

- [OKF-SPEC](./OKF-SPEC.md)
- [Contratos](./contracts/)
- [Modelos](./data_models/)
"""

# Carpeta NO enlazada desde index.md: nodos aca son huerfanos reales.
ORPHAN_REL = 'lonely/orphan.md'


def _fm(type_, title, desc, tags):
    return (
        "---\n"
        "type: '{}'\n"
        "title: '{}'\n"
        "description: '{}'\n"
        "tags: {}\n"
        "---\n\n"
        "# {}\n"
    ).format(type_, title, desc, tags, title)


VALID_NODE = _fm('Concept', 'Nodo A', 'desc del nodo a', "['tag1', 'tag2']") + \
    "Enlaza a [spec](./OKF-SPEC.md).\n"

OKF_SPEC_NODE = _fm('Concept', 'Espec OKF', 'spec', "['spec']") + "Spec.\n"


def _write(d, rel, content):
    path = os.path.join(d, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)
    return path


def _build_valid_kb(d):
    """KB minima valida: index + OKF-SPEC (enlazado) + un contrato enlazado via carpeta."""
    _write(d, 'index.md', INDEX_BODY)
    _write(d, 'OKF-SPEC.md', OKF_SPEC_NODE)
    _write(d, 'contracts/sample.md',
           _fm('Task Contract', 'Sample', 'desc', "['ccdd']")
           + "Ver [spec](../OKF-SPEC.md).\n")
    _write(d, 'data_models/users.md',
           _fm('Data Model', 'Users', 'desc', "['users']")
           + "Ver [spec](../OKF-SPEC.md).\n")


def _rules(findings):
    return {f['rule'] for f in findings if f['level'] == 'ERROR'}


def _files(findings):
    return {f['file'] for f in findings if f['level'] == 'ERROR'}


# ---------------------------------------------------------------------------
# Tests de la API
# ---------------------------------------------------------------------------

class TestValidKB(unittest.TestCase):
    def test_valid_kb_no_findings(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            findings = vo.validate_okf(d)
            self.assertEqual(findings, [], msg=findings)

    def test_real_kb_passes_clean(self):
        kb = os.path.join(ROOT, 'knowledge')
        findings = vo.validate_okf(kb)
        errors = [f for f in findings if f['level'] == 'ERROR']
        self.assertEqual(errors, [], msg=errors)


class TestOrphans(unittest.TestCase):
    def test_orphan_node_is_error_named(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, ORPHAN_REL,
                   _fm('Task Contract', 'Orphan', 'desc', "['x']")
                   + "Nadie me enlaza.\n")
            findings = vo.validate_okf(d)
            rules = _rules(findings)
            self.assertIn('ORPHAN', rules)
            self.assertIn('lonely/orphan.md', _files(findings))

    def test_node_reachable_via_folder_link(self):
        # index enlaza ./contracts/ ; un .md en contracts/ es alcanzable.
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/extra.md',
                   _fm('Task Contract', 'Extra', 'desc', "['x']")
                   + "En carpeta enlazada.\n")
            findings = vo.validate_okf(d)
            self.assertNotIn('ORPHAN', _rules(findings), msg=findings)


class TestBrokenLinks(unittest.TestCase):
    def test_broken_internal_link_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/badlink.md',
                   _fm('Task Contract', 'BadLink', 'desc', "['x']")
                   + "Enlace [roto](./no-existe.md) falla.\n")
            findings = vo.validate_okf(d)
            rules = _rules(findings)
            self.assertIn('LINK', rules)
            # origen y destino en el mensaje
            link = [f for f in findings if f['rule'] == 'LINK'][0]
            self.assertIn('no-existe.md', link['msg'])

    def test_external_link_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/ext.md',
                   _fm('Task Contract', 'Ext', 'desc', "['x']")
                   + "Ver [docs](https://example.com/x) y [repo](../OKF-SPEC.md).\n")
            findings = vo.validate_okf(d)
            self.assertNotIn('LINK', _rules(findings), msg=findings)

    def test_link_in_code_span_ignored(self):
        # `[roto](./no-existe.md)` dentro de backticks NO es un enlace real.
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/code.md',
                   _fm('Task Contract', 'Code', 'desc', "['x']")
                   + "Ejemplo: `[roto](./no-existe.md)` no cuenta.\n")
            findings = vo.validate_okf(d)
            self.assertNotIn('LINK', _rules(findings), msg=findings)


class TestFrontmatter(unittest.TestCase):
    def test_missing_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/nofm.md', "# Sin frontmatter\nnodo\n")
            findings = vo.validate_okf(d)
            self.assertIn('FM', _rules(findings))

    def test_broken_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/unclosed.md',
                   "---\ntype: 'Concept'\ntitle: 'X'\n")  # sin closing ---
            findings = vo.validate_okf(d)
            self.assertIn('FM', _rules(findings))

    def test_missing_required_key(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            bad = ("---\ntype: 'Concept'\ntitle: 'X'\ntags: ['a']\n---\n\n# X\n")
            _write(d, 'contracts/nokey.md', bad)  # sin description
            findings = vo.validate_okf(d)
            rules = _rules(findings)
            self.assertIn('FM_KEY', rules)
            self.assertTrue(any('description' in f['msg']
                                for f in findings if f['rule'] == 'FM_KEY'),
                            msg=findings)


class TestType(unittest.TestCase):
    def test_invalid_type_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/badtype.md',
                   _fm('Otra Cosa', 'BadType', 'desc', "['x']")
                   + "x\n")
            findings = vo.validate_okf(d)
            self.assertIn('TYPE', _rules(findings))

    def test_all_valid_types_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            index = ("# KB\n"
                     "- [a](./a.md)\n- [b](./b.md)\n"
                     "- [c](./c.md)\n- [d](./d.md)\n")
            _write(d, 'index.md', index)
            _write(d, 'a.md', _fm('Task Contract', 'A', 'd', "['x']") + "x\n")
            _write(d, 'b.md', _fm('Data Model', 'B', 'd', "['x']") + "x\n")
            _write(d, 'c.md', _fm('Architecture', 'C', 'd', "['x']") + "x\n")
            _write(d, 'd.md', _fm('Concept', 'D', 'd', "['x']") + "x\n")
            findings = vo.validate_okf(d)
            self.assertEqual(findings, [], msg=findings)


class TestTags(unittest.TestCase):
    def test_empty_tags_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/emptytags.md',
                   _fm('Task Contract', 'ET', 'desc', "[]") + "x\n")
            findings = vo.validate_okf(d)
            self.assertIn('TAGS', _rules(findings))

    def test_uppercase_tags_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/uptags.md',
                   _fm('Task Contract', 'UT', 'desc', "['UPPER']") + "x\n")
            findings = vo.validate_okf(d)
            self.assertIn('TAGS', _rules(findings))


class TestDeterminism(unittest.TestCase):
    def test_findings_sorted_by_file_then_rule(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/z.md',
                   _fm('BadType', 'Z', 'desc', "['UPPER']") + "x\n")  # TYPE + TAGS
            _write(d, 'contracts/a.md',
                   _fm('BadType', 'A', 'desc', "[]") + "x\n")  # TYPE + TAGS
            findings = [f for f in vo.validate_okf(d) if f['level'] == 'ERROR'
                        and f['file'].startswith('contracts/')]
            keys = [(f['file'], f['rule']) for f in findings]
            self.assertEqual(keys, sorted(keys))


# ---------------------------------------------------------------------------
# Tests del CLI (subprocess permitido en tests)
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):
    def _run_cli(self, d):
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'scripts', 'validate_okf.py'), d],
            capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def test_cli_exit_zero_on_valid(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            rc, out = self._run_cli(d)
            self.assertEqual(rc, 0, msg=out)
            self.assertIn('Resumen', out)

    def test_cli_exit_one_on_orphan(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, ORPHAN_REL,
                   _fm('Task Contract', 'Orphan', 'desc', "['x']")
                   + "nadie me enlaza\n")
            rc, out = self._run_cli(d)
            self.assertEqual(rc, 1, msg=out)
            self.assertIn('ORPHAN', out)
            self.assertIn('lonely/orphan.md', out)

    def test_cli_exit_one_on_broken_link(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/badlink.md',
                   _fm('Task Contract', 'BadLink', 'desc', "['x']")
                   + "[roto](./no-existe.md)\n")
            rc, out = self._run_cli(d)
            self.assertEqual(rc, 1, msg=out)
            self.assertIn('LINK', out)

    def test_cli_exit_one_on_bad_type(self):
        with tempfile.TemporaryDirectory() as d:
            _build_valid_kb(d)
            _write(d, 'contracts/badtype.md',
                   _fm('Otra Cosa', 'BadType', 'desc', "['x']") + "x\n")
            rc, out = self._run_cli(d)
            self.assertEqual(rc, 1, msg=out)
            self.assertIn('TYPE', out)


if __name__ == '__main__':
    unittest.main()