"""Tests para lint_ascii (Contrato 13).

Fixtures en tempdir: violacion -> ERROR con linea y codepoint; mismo literal
con pragma allow -> pasa; docstring con acentos -> pasa; skip-file -> pasa y
el resumen lo declara; f-string con no-ASCII -> ERROR; scripts/ real del repo
-> limpio; exit codes del CLI; orden por (archivo, linea).
"""

import os
import subprocess
import sys
import tempfile
import unittest

# Agregar scripts/ al PATH para importar lint_ascii
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from lint_ascii import lint_ascii, _lint_dir


class TestLintAscii(unittest.TestCase):
    """Tests de linter ASCII."""

    def test_violation_linea_and_codepoint(self):
        """Fixture con 'inválido' en literal -> ERROR nombrando linea y codepoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_violation.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('msg = "inválido"\n')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 1)
            f = findings[0]
            self.assertEqual(f['level'], 'ERROR')
            self.assertEqual(f['rule'], 'ASCII')
            self.assertIn('linea 1', f['msg'])
            self.assertIn('U+00E1', f['msg'])

    def test_api_returns_list(self):
        """lint_ascii devuelve una LISTA (signature del contrato)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_clean.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('msg = "hello"\n')
            result = lint_ascii(tmpdir)
            self.assertIsInstance(result, list)
            self.assertEqual(result, [])

    def test_pragma_allow_permits(self):
        """Mismo literal con '# ascii: allow' -> pasa."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_allow.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('msg = "inválido"  # ascii: allow\n')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 0)

    def test_docstring_excluded(self):
        """Docstring con acentos -> pasa (excluido)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_docstring.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('"""Validacion basica."""\n')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 0)

    def test_class_docstring_excluded(self):
        """Docstring de clase con acentos -> pasa."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_class_doc.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('''class Foo:
    """Descripcion aqui."""
    pass
''')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 0)

    def test_function_docstring_excluded(self):
        """Docstring de funcion con acentos -> pasa."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_func_doc.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('''def foo():
    """Logica completa."""
    pass
''')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 0)

    def test_skip_file_pragma(self):
        """Archivo con '# ascii-lint: skip-file' en primeras 5 lineas -> pasa y se declara."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_skip.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('''# ascii-lint: skip-file
msg = "inválido"
''')
            findings, skipped = _lint_dir(tmpdir)
            self.assertEqual(len(findings), 0)
            self.assertIn('test_skip.py', skipped)
            # La API publica tambien pasa limpio
            self.assertEqual(lint_ascii(tmpdir), [])

    def test_skip_file_declared_in_cli_summary(self):
        """CLI: el resumen declara el archivo salteado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_skip.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('''# ascii-lint: skip-file
msg = "inválido"
''')
            result = subprocess.run(
                [sys.executable, 'scripts/lint_ascii.py', tmpdir],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True, text=True, encoding='utf-8'
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn('test_skip.py', result.stdout)
            self.assertIn('salteados', result.stdout)

    def test_f_string_literal_non_ascii(self):
        """F-string con parte literal no-ASCII -> ERROR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_fstring.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('name = "test"\nmsg = f"Resultado: {name} inválido"\n')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 1)
            f = findings[0]
            self.assertIn('f-string', f['msg'])
            self.assertIn('U+00E1', f['msg'])

    def test_real_scripts_dir_is_clean(self):
        """Scripts real del repo debe estar limpio."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scripts_dir = os.path.join(repo_root, 'scripts')
        findings = lint_ascii(scripts_dir)
        errors = [f for f in findings if f['level'] == 'ERROR']
        self.assertEqual(len(errors), 0, msg='Real scripts/ tiene errores: {}'.format(errors))

    def test_cli_exit_code_zero(self):
        """CLI: exit 0 sin ERRORs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_clean.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('msg = "hello"\n')
            result = subprocess.run(
                [sys.executable, 'scripts/lint_ascii.py', tmpdir],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True
            )
            self.assertEqual(result.returncode, 0)

    def test_cli_exit_code_one(self):
        """CLI: exit 1 con >=1 ERROR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_error.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('msg = "inválido"\n')
            result = subprocess.run(
                [sys.executable, 'scripts/lint_ascii.py', tmpdir],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True
            )
            self.assertEqual(result.returncode, 1)

    def test_multiple_violations(self):
        """Multiples violaciones en un archivo -> todos reportados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_multi.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('''msg1 = "inválido"
msg2 = "error"
msg3 = "fallo"
''')
            findings = lint_ascii(tmpdir)
            # Solo linea 1 tiene no-ASCII
            self.assertEqual(len(findings), 1)
            self.assertIn('linea 1', findings[0]['msg'])

    def test_ordered_by_file(self):
        """Findings ordenados por archivo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, 'a_file.py')
            with open(f1, 'w', encoding='utf-8') as f:
                f.write('msg = "inválido"\n')
            f2 = os.path.join(tmpdir, 'z_file.py')
            with open(f2, 'w', encoding='utf-8') as f:
                f.write('msg = "más"\n')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 2)
            files_in_order = [f['file'] for f in findings]
            self.assertTrue(files_in_order[0].startswith('a_'))
            self.assertTrue(files_in_order[1].startswith('z_'))

    def test_ordered_by_line_across_kinds(self):
        """F-string en linea 2 y Constant en linea 10 -> findings en orden 2, 10."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_order.py')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('''name = "x"
msg_f = f"paso {name} inválido"
a = 1
b = 2
c = 3
d = 4
e = 5
g = 6
h = 7
msg_c = "también"
''')
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 2)
            self.assertIn('linea 2', findings[0]['msg'])
            self.assertIn('f-string', findings[0]['msg'])
            self.assertIn('linea 10', findings[1]['msg'])
            self.assertIn('literal string', findings[1]['msg'])

    def test_empty_directory(self):
        """Directorio vacio -> OK, sin findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            findings = lint_ascii(tmpdir)
            self.assertEqual(len(findings), 0)

    def test_nonexistent_directory(self):
        """Directorio inexistente -> OK, sin lanzar."""
        findings = lint_ascii('/nonexistent/path/12345')
        self.assertEqual(findings, [])

    def test_archivo_no_utf8_es_finding_no_crash(self):
        """H-4: un archivo con bytes invalidos para UTF-8 no tumba el gate.

        Antes del fix ``open(..., encoding='utf-8')`` lanzaba UnicodeDecodeError
        (ValueError, no OSError -> no capturado) y abortaba todo el gate con
        traceback. Un archivo no-UTF8 es por definicion no-ASCII-conforme: se
        reporta como finding del archivo y el gate sigue con los demas.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = os.path.join(tmpdir, 'bad.py')
            with open(bad, 'wb') as f:
                f.write(b'x = "caf\xe9"\n')
            good = os.path.join(tmpdir, 'good.py')
            with open(good, 'w', encoding='utf-8') as f:
                f.write('y = "ok"\n')
            findings = lint_ascii(tmpdir)
            files = [f['file'] for f in findings]
            self.assertIn('bad.py', files)
            self.assertNotIn('good.py', files)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]['level'], 'ERROR')
            self.assertEqual(findings[0]['rule'], 'ASCII')


if __name__ == '__main__':
    unittest.main()
