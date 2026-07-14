"""Oraculo congelado del gate de secretos (Contrato: secret-scan-gate).

Fija el comportamiento de ``scripts/scan_secrets.py``: escaneo determinista
(regex stdlib, sin red/subprocess/LLM) de literales string en archivos de
texto buscando patrones de credenciales conocidas (prefijos de key de
proveedores concretos + bloques de private key), NO deteccion de alta
entropia generica (evita falsos positivos masivos contra los ``tests_sha256``
de 64 hex chars que ya viven en ``knowledge/contracts/*.md`` en este repo).

  API:
    ``PATTERNS`` — lista de ``(rule_name, compiled_regex)``. Cada patron
      matchea el secreto completo (no solo el prefijo) para que el finding
      incluya el texto detectado.
        - AWS_KEY: ``AKIA[0-9A-Z]{16}``
        - GITHUB_TOKEN: ``gh[pousr]_[A-Za-z0-9]{36,}``
        - SLACK_TOKEN: ``xox[baprs]-[A-Za-z0-9-]{10,}``
        - GOOGLE_API_KEY: ``AIza[0-9A-Za-z_-]{35}``
        - STRIPE_KEY: ``(sk|pk)_live_[A-Za-z0-9]{20,}``
        - PRIVATE_KEY_BLOCK: ``-----BEGIN [A-Z ]*PRIVATE KEY-----``
    ``scan_text(text) -> [{'rule','match','line'}]`` — un item por cada
      match de cualquier patron en ``PATTERNS``, con el numero de linea
      (1-indexed) y el texto exacto matcheado. Ordenado por (line, rule).
    ``scan_file(path) -> [{'file','level','rule','msg'}]`` — findings ERROR
      de ``scan_text`` sobre el contenido de ``path`` (lectura UTF-8,
      errors='ignore' para no romper en binarios). ``msg`` incluye la regla
      y el numero de linea, NO el secreto completo (evita filtrarlo en logs
      de CI: solo los primeros 8 chars + '...').
    ``scan_directory(directory, extensions=('.py','.js','.ts','.md','.json'))
      -> [{'file','level','rule','msg'}]`` — recorre ``directory``
      recursivamente (``os.walk``), escanea archivos cuya extension (en
      minuscula) esta en ``extensions``, ignora directorios ocultos
      (nombre empieza con ``.``) y ``__pycache__``/``node_modules``.
      Ordenado por (file, line implicito en msg).
    ``main(argv) -> int`` — ``argv[1:]`` son uno o mas directorios (default
      ``['src', 'tests']`` si no se pasa ninguno). Imprime cada finding
      (``str``: ``"ERROR [<rule>] <file>: <msg>"``) y devuelve 0 si no hay
      findings, 1 si hay >=1.

Ningun fixture de este oraculo usa una credencial real: son cadenas con la
FORMA correcta del patron pero generadas para el test.
"""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import scan_secrets as ss  # noqa: E402


def _write(path, content):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)


class TestScanText(unittest.TestCase):
    def test_no_matches_on_clean_text(self):
        text = "def hello():\n    return 'Hello, World'\n"
        self.assertEqual(ss.scan_text(text), [])

    def test_aws_key_detected_with_line(self):
        text = "line1\nkey = 'AKIAABCDEFGHIJKLMNOP'\nline3\n"
        result = ss.scan_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['rule'], 'AWS_KEY')
        self.assertEqual(result[0]['line'], 2)
        self.assertEqual(result[0]['match'], 'AKIAABCDEFGHIJKLMNOP')

    def test_github_token_detected(self):
        text = 'token = "ghp_' + 'a' * 36 + '"'
        result = ss.scan_text(text)
        self.assertTrue(any(r['rule'] == 'GITHUB_TOKEN' for r in result))

    def test_slack_token_detected(self):
        text = 'token = "xoxb-1234567890-abcdefghij"'
        result = ss.scan_text(text)
        self.assertTrue(any(r['rule'] == 'SLACK_TOKEN' for r in result))

    def test_google_api_key_detected(self):
        text = 'key = "AIza' + 'B' * 35 + '"'
        result = ss.scan_text(text)
        self.assertTrue(any(r['rule'] == 'GOOGLE_API_KEY' for r in result))

    def test_stripe_key_detected(self):
        text = 'key = "sk_live_' + 'c' * 24 + '"'
        result = ss.scan_text(text)
        self.assertTrue(any(r['rule'] == 'STRIPE_KEY' for r in result))

    def test_private_key_block_detected(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIExyz\n-----END RSA PRIVATE KEY-----\n"
        result = ss.scan_text(text)
        self.assertTrue(any(r['rule'] == 'PRIVATE_KEY_BLOCK' for r in result))

    def test_sha256_hash_is_not_flagged(self):
        # Regresion explicita: los tests_sha256 de 64 hex chars de este
        # repo NO deben dispararse como falso positivo.
        text = 'tests_sha256: "e0ef690cc83b80f9192b6d500c86962d3d88ebf138bbf1a4d696bb7abdeb90a9"'
        self.assertEqual(ss.scan_text(text), [])

    def test_multiple_matches_sorted_by_line_then_rule(self):
        text = (
            "a = 'AKIAABCDEFGHIJKLMNOP'\n"
            "b = 'xoxb-1234567890-abcdefghij'\n"
        )
        result = ss.scan_text(text)
        self.assertEqual([r['line'] for r in result], [1, 2])


class TestScanFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finding_shape_and_truncated_secret(self):
        path = os.path.join(self.tmp, 'leak.py')
        _write(path, "key = 'AKIAABCDEFGHIJKLMNOP'\n")
        findings = ss.scan_file(path)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f['level'], 'ERROR')
        self.assertEqual(f['rule'], 'AWS_KEY')
        self.assertEqual(f['file'], path)
        # El secreto completo NUNCA aparece entero en el mensaje.
        self.assertNotIn('AKIAABCDEFGHIJKLMNOP', f['msg'])
        self.assertIn('AKIAABCD', f['msg'])

    def test_clean_file_no_findings(self):
        path = os.path.join(self.tmp, 'clean.py')
        _write(path, "def f():\n    return 1\n")
        self.assertEqual(ss.scan_file(path), [])

    def test_unreadable_binary_does_not_crash(self):
        path = os.path.join(self.tmp, 'bin.py')
        with open(path, 'wb') as fh:
            fh.write(b'\xff\xfe\x00\x01binary junk')
        # No debe lanzar excepcion; puede o no encontrar findings.
        result = ss.scan_file(path)
        self.assertIsInstance(result, list)


class TestScanDirectory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finds_leak_in_py_file(self):
        _write(os.path.join(self.tmp, 'src', 'a.py'), "k = 'AKIAABCDEFGHIJKLMNOP'\n")
        findings = ss.scan_directory(self.tmp)
        self.assertEqual(len(findings), 1)

    def test_ignores_extension_not_in_list(self):
        _write(os.path.join(self.tmp, 'a.bin'), "k = 'AKIAABCDEFGHIJKLMNOP'\n")
        findings = ss.scan_directory(self.tmp)
        self.assertEqual(findings, [])

    def test_ignores_hidden_dirs_and_pycache(self):
        _write(os.path.join(self.tmp, '.git', 'x.py'), "k = 'AKIAABCDEFGHIJKLMNOP'\n")
        _write(os.path.join(self.tmp, '__pycache__', 'x.py'), "k = 'AKIAABCDEFGHIJKLMNOP'\n")
        _write(os.path.join(self.tmp, 'node_modules', 'x.py'), "k = 'AKIAABCDEFGHIJKLMNOP'\n")
        findings = ss.scan_directory(self.tmp)
        self.assertEqual(findings, [])

    def test_nonexistent_directory_returns_empty(self):
        findings = ss.scan_directory(os.path.join(self.tmp, 'does_not_exist'))
        self.assertEqual(findings, [])

    def test_custom_extensions(self):
        _write(os.path.join(self.tmp, 'a.rs'), "let k = \"AKIAABCDEFGHIJKLMNOP\";\n")
        self.assertEqual(ss.scan_directory(self.tmp), [])
        findings = ss.scan_directory(self.tmp, extensions=('.rs',))
        self.assertEqual(len(findings), 1)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_dirs_return_0(self):
        src = os.path.join(self.tmp, 'src')
        tests = os.path.join(self.tmp, 'tests')
        _write(os.path.join(src, 'a.py'), "def f(): return 1\n")
        _write(os.path.join(tests, 'test_a.py'), "def test(): assert True\n")
        code = ss.main(['prog', src, tests])
        self.assertEqual(code, 0)

    def test_leak_returns_1(self):
        src = os.path.join(self.tmp, 'src')
        _write(os.path.join(src, 'a.py'), "k = 'AKIAABCDEFGHIJKLMNOP'\n")
        code = ss.main(['prog', src])
        self.assertEqual(code, 1)

    def test_no_args_defaults_to_src_and_tests(self):
        # Sin argumentos, default ('src', 'tests') relativos al cwd; ambos
        # ausentes en un tmpdir vacio -> sin findings -> exit 0.
        cwd = os.getcwd()
        os.chdir(self.tmp)
        try:
            code = ss.main(['prog'])
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
