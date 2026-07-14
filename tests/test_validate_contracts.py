"""Tests unitarios del validador de contratos KDD.

Usa fixtures propias generadas en un tempdir; NO depende del contenido real
de knowledge/contracts/.
"""

import os
import sys
import tempfile
import unittest
from io import StringIO

# hacer importable el modulo scripts/validate_contracts.py
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import validate_contracts as vc  # noqa: E402


VALID_CONTRACT = """---
type: 'Task Contract'
title: 'Demo'
task: hello_world
intent: "Demostrar structura."
target: src/hello.py
signature: "def hello(name: str) -> str:"
test_command: "python -m unittest tests/test_sample.py"
budget:
  max_cyclomatic_complexity: 2
  max_nesting_depth: 1
tests: "tests/test_sample.py"
tests_sha256: "c11c4064b2030dac8352c6453a128af2aedcb3ecc711aed805f22768cf54fda4"
touch_only: ['src/hello.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: Hello World

## Intent
Implementar una funcion que retorne un saludo.

## Interface
```python
def hello(name: str) -> str:
    ...
```

## Invariants
- La funcion no lanza excepciones.

## Examples
- `hello("A")` -> `"Hello, A"`
- `hello("B")` -> `"Hello, B"`

## Do / Don't
- DO: Usar f-strings.

## Tests
Los tests estan en tests/test_sample.py

## Constraints
- PARAR y reportar si necesitas conectarte a la red.
"""


def _write(d, name, content):
    """Escribe archivo creando directorios padre si es necesario."""
    p = os.path.join(d, name)
    parent = os.path.dirname(p)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write(content)
    return p


class TestFrontmatterParser(unittest.TestCase):
    def test_parse_scalars_and_lists(self):
        text = "---\nkey: value\nlist: ['a', 'b']\nq: \"quoted\"\n---\nbody"
        data, body = vc.parse_frontmatter(text)
        self.assertEqual(data['key'], 'value')
        self.assertEqual(data['list'], ['a', 'b'])
        self.assertEqual(data['q'], 'quoted')
        self.assertIn('body', body)

    def test_nested_dict_by_indent(self):
        text = ("---\nbudget:\n  max_cyclomatic_complexity: 2\n"
                "  max_nesting_depth: 1\ntop: yes\n---\n")
        data, _ = vc.parse_frontmatter(text)
        self.assertEqual(data['budget'],
                         {'max_cyclomatic_complexity': '2', 'max_nesting_depth': '1'})
        self.assertEqual(data['top'], 'yes')

    def test_missing_frontmatter(self):
        data, _ = vc.parse_frontmatter("# solo cuerpo\n## Intent\nx")
        self.assertIsNone(data)

    def test_unclosed_frontmatter(self):
        data, _ = vc.parse_frontmatter("---\ntask: x\n")
        self.assertIsNone(data)


class TestValidatorValid(unittest.TestCase):
    def test_valid_contract_no_errors(self):
        with tempfile.TemporaryDirectory() as repo_root:
            # Crear estructura completa: contracts/, src/, tests/
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/ok.md', VALID_CONTRACT)
            _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
            _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')

            findings = vc.validate_directory(contracts_dir, repo_root=repo_root)
            errors = [f for f in findings if f.level == 'ERROR']
            self.assertEqual(errors, [], msg=[str(f) for f in findings])

    def test_template_prefix_is_skipped(self):
        """TEMPLATE-*.md no es un contrato real (mismo criterio que specs/TEMPLATE-CONTRACT.md
        en validate_specs.py): se ignora aunque este mal formado, para poder vivir en
        knowledge/contracts/ como plantilla sin romper el gate."""
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/ok.md', VALID_CONTRACT)
            _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
            _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')
            _write(repo_root, 'knowledge/contracts/TEMPLATE-task-contract.md', '<placeholder, no es YAML valido>')

            findings = vc.validate_directory(contracts_dir, repo_root=repo_root)
            errors = [f for f in findings if f.level == 'ERROR']
            self.assertEqual(errors, [], msg=[str(f) for f in findings])
            self.assertFalse(any('TEMPLATE-' in f.file for f in findings))

    def test_fixture_integro_sin_errores(self):
        """Fixture completo con estructura repo_root válida debe pasar sin errores."""
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/complete.md', VALID_CONTRACT)
            _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
            _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')

            findings = vc.validate_directory(contracts_dir, repo_root=repo_root)
            errors = [f for f in findings if f.level == 'ERROR']
            self.assertEqual(errors, [], msg=[str(f) for f in findings])


class TestValidatorErrors(unittest.TestCase):
    def _run(self, content, create_files=True):
        """Ejecuta validación sobre estructura temporal.

        Si create_files=True, crea src/hello.py y tests/test_sample.py.
        """
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/c.md', content)
            if create_files:
                _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
                _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')
            return vc.validate_directory(contracts_dir, repo_root=repo_root)

    def _rules(self, findings):
        return {f.rule for f in findings if f.level == 'ERROR'}

    def test_missing_required_key(self):
        # quitar test_command
        bad = VALID_CONTRACT.replace('test_command: "python -m unittest tests/test_sample.py"\n',
                                     '')
        rules = self._rules(self._run(bad))
        self.assertIn('FM_KEY_test_command', rules)

    def test_wrong_type(self):
        bad = VALID_CONTRACT.replace("type: 'Task Contract'", "type: 'Otra cosa'")
        rules = self._rules(self._run(bad))
        self.assertIn('FM_KEY_type', rules)

    def test_empty_required_key(self):
        bad = VALID_CONTRACT.replace('task: hello_world', 'task: ')
        rules = self._rules(self._run(bad))
        self.assertIn('FM_KEY_task', rules)

    def test_missing_section(self):
        bad = VALID_CONTRACT.replace('## Invariants\n- La funcion no lanza excepciones.\n',
                                     '')
        rules = self._rules(self._run(bad))
        self.assertIn('SEC_Invariants', rules)

    def test_examples_too_few_items(self):
        bad = VALID_CONTRACT.replace(
            '## Examples\n- `hello("A")` -> `"Hello, A"`\n- `hello("B")` -> `"Hello, B"`\n',
            '## Examples\n- `hello("A")` -> `"Hello, A"`\n')
        findings = self._run(bad)
        rules = self._rules(findings)
        self.assertIn('SEC_Examples', rules)

    def test_constraints_missing_phrase(self):
        bad = VALID_CONTRACT.replace(
            '## Constraints\n- PARAR y reportar si necesitas conectarte a la red.\n',
            '## Constraints\n- Evitar la red.\n')
        rules = self._rules(self._run(bad))
        self.assertIn('SEC_Constraints', rules)

    def test_unparseable_frontmatter(self):
        bad = "# no frontmatter\n## Intent\nx"
        rules = self._rules(self._run(bad))
        self.assertIn('FM_PARSE', rules)

    def test_target_inexistente(self):
        """target inexistente debe dar error FM_PATH_target."""
        bad = VALID_CONTRACT.replace('target: src/hello.py', 'target: src/nonexistent.py')
        rules = self._rules(self._run(bad))
        self.assertIn('FM_PATH_target', rules)

    def test_tests_inexistente(self):
        """tests inexistente debe dar error FM_PATH_tests."""
        bad = VALID_CONTRACT.replace('tests: "tests/test_sample.py"', 'tests: "tests/nonexistent.py"')
        rules = self._rules(self._run(bad))
        self.assertIn('FM_PATH_tests', rules)

    def test_ambos_archivos_inexistentes(self):
        """Si tanto target como tests no existen, debe haber ambos errores."""
        bad = VALID_CONTRACT.replace('target: src/hello.py', 'target: src/nonexistent.py')
        bad = bad.replace('tests: "tests/test_sample.py"', 'tests: "tests/nonexistent.py"')
        rules = self._rules(self._run(bad))
        self.assertIn('FM_PATH_target', rules)
        self.assertIn('FM_PATH_tests', rules)


class TestTouchOnly(TestValidatorErrors):
    """Contrato 28: touch_only obligatoria — el perimetro como dato.

    Semantica: lista inline no vacia de rutas/patrones repo-relativos posix,
    matching fnmatch (un '*' cruza '/'). El target debe estar cubierto
    (FM_TOUCH_TARGET); el archivo `tests` NO debe estarlo (FM_TOUCH_TESTS,
    el oraculo queda fuera del perimetro) SALVO cuando tests == target (el
    entregable ES un test).
    """

    def test_touch_only_ausente_es_error(self):
        bad = VALID_CONTRACT.replace("touch_only: ['src/hello.py']\n", '')
        rules = self._rules(self._run(bad))
        self.assertIn('FM_KEY_touch_only', rules)

    def test_touch_only_forma_invalida(self):
        for raro in ("touch_only: src/hello.py",
                     "touch_only: []",
                     "touch_only: ['src/hello.py', '']"):
            bad = VALID_CONTRACT.replace("touch_only: ['src/hello.py']", raro)
            rules = self._rules(self._run(bad))
            self.assertIn('FM_TOUCH_ONLY', rules, raro)

    def test_target_no_cubierto_es_error(self):
        bad = VALID_CONTRACT.replace("touch_only: ['src/hello.py']",
                                     "touch_only: ['scripts/otro.py']")
        rules = self._rules(self._run(bad))
        self.assertIn('FM_TOUCH_TARGET', rules)

    def test_target_cubierto_por_glob(self):
        ok = VALID_CONTRACT.replace("touch_only: ['src/hello.py']",
                                    "touch_only: ['src/*']")
        findings = self._run(ok)
        errors = [f for f in findings if f.level == 'ERROR']
        self.assertEqual(errors, [], msg=[str(f) for f in errors])

    def test_oraculo_cubierto_es_error(self):
        bad = VALID_CONTRACT.replace(
            "touch_only: ['src/hello.py']",
            "touch_only: ['src/hello.py', 'tests/test_sample.py']")
        rules = self._rules(self._run(bad))
        self.assertIn('FM_TOUCH_TESTS', rules)

    def test_oraculo_cubierto_por_glob_es_error(self):
        bad = VALID_CONTRACT.replace("touch_only: ['src/hello.py']",
                                     "touch_only: ['src/hello.py', 'tests/*']")
        rules = self._rules(self._run(bad))
        self.assertIn('FM_TOUCH_TESTS', rules)

    def test_target_igual_a_tests_permitido(self):
        # El entregable ES un test (p. ej. agents-context-rule): touch_only
        # DEBE poder cubrirlo sin FM_TOUCH_TESTS.
        ok = VALID_CONTRACT.replace('target: src/hello.py',
                                    'target: tests/test_sample.py')
        ok = ok.replace("touch_only: ['src/hello.py']",
                        "touch_only: ['tests/test_sample.py']")
        findings = self._run(ok)
        rules = self._rules(findings)
        self.assertNotIn('FM_TOUCH_TESTS', rules)
        self.assertNotIn('FM_TOUCH_TARGET', rules)


class TestValidatorWarnings(unittest.TestCase):
    def test_missing_forbids_is_warning_not_error(self):
        bad = VALID_CONTRACT.replace("forbids: ['network', 'subprocess']\n", '')
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/c.md', bad)
            _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
            _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')
            findings = vc.validate_directory(contracts_dir, repo_root=repo_root)
        warnings = [f for f in findings if f.level == 'WARNING']
        errors = [f for f in findings if f.level == 'ERROR']
        self.assertTrue(any(f.rule == 'FM_KEY_forbids' for f in warnings))
        self.assertFalse(any(f.rule == 'FM_KEY_forbids' for f in errors))

    def test_empty_forbids_is_warning(self):
        bad = VALID_CONTRACT.replace("forbids: ['network', 'subprocess']", "forbids: []")
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/c.md', bad)
            _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
            _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')
            findings = vc.validate_directory(contracts_dir, repo_root=repo_root)
        warnings = [f for f in findings if f.level == 'WARNING']
        self.assertTrue(any(f.rule == 'FM_KEY_forbids' and 'vacia' in f.message
                            for f in warnings))


class TestTestsSha256Validation(unittest.TestCase):
    """Tests para validación de tests_sha256 (FREEZE-ORACLE)."""

    def _run(self, content, create_files=True):
        """Ejecuta validación sobre estructura temporal."""
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/c.md', content)
            if create_files:
                _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
                _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')
            return vc.validate_directory(contracts_dir, repo_root=repo_root)

    def _rules_and_messages(self, findings):
        return {(f.rule, f.message) for f in findings}

    def test_sha256_correct_no_errors(self):
        """(a) hash correcto → 0 errores"""
        # Calcular hash real del test file
        test_content = 'import unittest\nclass TestHello(unittest.TestCase): pass\n'
        normalized = test_content.replace('\r\n', '\n').replace('\r', '\n')
        import hashlib
        correct_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()

        contract = VALID_CONTRACT.replace(
            'forbids: [\'network\', \'subprocess\']',
            f'forbids: [\'network\', \'subprocess\']\ntests_sha256: "{correct_hash}"'
        )
        findings = self._run(contract)
        errors = [f for f in findings if f.level == 'ERROR']
        self.assertEqual(errors, [], msg=[str(f) for f in findings])

    def test_sha256_mismatch_error(self):
        """(b) contenido mutado → ERROR FM_TESTS_FROZEN con ambos hashes"""
        import hashlib
        wrong_hash = hashlib.sha256(b'different_content').hexdigest()

        contract = VALID_CONTRACT.replace(
            'forbids: [\'network\', \'subprocess\']',
            f'forbids: [\'network\', \'subprocess\']\ntests_sha256: "{wrong_hash}"'
        )
        findings = self._run(contract)
        errors = [f for f in findings if f.level == 'ERROR']
        fm_tests_frozen_errors = [f for f in errors if f.rule == 'FM_TESTS_FROZEN']
        self.assertTrue(len(fm_tests_frozen_errors) >= 1, msg=[str(f) for f in findings])
        # Verificar que el mensaje menciona el archivo y ambos hashes
        msg = fm_tests_frozen_errors[0].message
        self.assertIn('tests/test_sample.py', msg)
        self.assertIn(wrong_hash, msg)

    def test_sha256_absent_error(self):
        """(c) clave ausente → ERROR FM_TESTS_FROZEN con comando --hash"""
        # Crear contrato sin tests_sha256
        contract_without_hash = VALID_CONTRACT.replace(
            'tests_sha256: "c11c4064b2030dac8352c6453a128af2aedcb3ecc711aed805f22768cf54fda4"\n',
            ''
        )
        findings = self._run(contract_without_hash)
        errors = [f for f in findings if f.level == 'ERROR']
        fm_tests_frozen_errors = [f for f in errors if f.rule == 'FM_TESTS_FROZEN']
        self.assertTrue(len(fm_tests_frozen_errors) >= 1, msg=[str(f) for f in findings])
        # Verificar que el mensaje menciona --hash
        self.assertIn('--hash', fm_tests_frozen_errors[0].message)

    def test_sha256_crlf_vs_lf_same_hash(self):
        """(d) hash con CRLF vs LF → normalización funciona"""
        # Crear fixture con CRLF
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)

            # Escribir archivo con LF
            _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')

            # Calcular hash del contenido con LF
            test_content_lf = 'import unittest\nclass TestHello(unittest.TestCase): pass\n'
            normalized = test_content_lf.replace('\r\n', '\n').replace('\r', '\n')
            import hashlib
            correct_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()

            # Escribir test file CON CRLF
            test_path = os.path.join(repo_root, 'tests/test_sample.py')
            os.makedirs(os.path.dirname(test_path), exist_ok=True)
            with open(test_path, 'wb') as f:
                f.write(b'import unittest\r\nclass TestHello(unittest.TestCase): pass\r\n')

            contract = VALID_CONTRACT.replace(
                'forbids: [\'network\', \'subprocess\']',
                f'forbids: [\'network\', \'subprocess\']\ntests_sha256: "{correct_hash}"'
            )
            _write(repo_root, 'knowledge/contracts/c.md', contract)

            findings = vc.validate_directory(contracts_dir, repo_root=repo_root)
            errors = [f for f in findings if f.level == 'ERROR']
            # La normalización debe hacer que el hash coincida
            self.assertEqual(errors, [], msg=[str(f) for f in findings])

    def test_sha256_invalid_format_error(self):
        """(e) formato inválido → ERROR"""
        # Hash con menos de 64 caracteres
        contract = VALID_CONTRACT.replace(
            'forbids: [\'network\', \'subprocess\']',
            'forbids: [\'network\', \'subprocess\']\ntests_sha256: "abcd1234"'
        )
        findings = self._run(contract)
        errors = [f for f in findings if f.level == 'ERROR']
        fm_tests_frozen_errors = [f for f in errors if f.rule == 'FM_TESTS_FROZEN']
        self.assertTrue(len(fm_tests_frozen_errors) >= 1, msg=[str(f) for f in findings])
        self.assertIn('formato invalido', fm_tests_frozen_errors[0].message)

    def test_sha256_invalid_hex_characters(self):
        """Hash con caracteres no-hex → ERROR"""
        # 64 caracteres pero contiene 'Z' (no hex)
        bad_hash = 'Z' * 64
        contract = VALID_CONTRACT.replace(
            'forbids: [\'network\', \'subprocess\']',
            f'forbids: [\'network\', \'subprocess\']\ntests_sha256: "{bad_hash}"'
        )
        findings = self._run(contract)
        errors = [f for f in findings if f.level == 'ERROR']
        fm_tests_frozen_errors = [f for f in errors if f.rule == 'FM_TESTS_FROZEN']
        self.assertTrue(len(fm_tests_frozen_errors) >= 1, msg=[str(f) for f in findings])

    def test_sha256_present_but_tests_missing(self):
        """Si tests_sha256 presente pero tests no existe, FM_PATH_tests reporta (no duplica hash error)"""
        import hashlib
        correct_hash = hashlib.sha256(b'dummy').hexdigest()

        contract = VALID_CONTRACT.replace(
            'tests: "tests/test_sample.py"',
            f'tests: "tests/nonexistent.py"'
        ).replace(
            'forbids: [\'network\', \'subprocess\']',
            f'forbids: [\'network\', \'subprocess\']\ntests_sha256: "{correct_hash}"'
        )
        findings = self._run(contract, create_files=False)
        errors = [f for f in findings if f.level == 'ERROR']
        # Debe haber FM_PATH_tests pero no duplicar el error hash
        rules = {f.rule for f in errors}
        self.assertIn('FM_PATH_tests', rules)


class TestHashHelper(unittest.TestCase):
    """Tests para el helper --hash CLI."""

    def test_hash_helper_prints_correct_hash(self):
        """--hash imprime el SHA256 correcto del archivo (64 hex)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.py')
            test_content = 'import unittest\nclass TestHello(unittest.TestCase): pass\n'
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_content)

            # Capturar salida del helper
            real_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                rc = vc.main(['prog', '--hash', test_file])
                output = sys.stdout.getvalue().strip()
            finally:
                sys.stdout = real_stdout

            # Verificar exit code 0 y output es 64 hex
            self.assertEqual(rc, 0)
            self.assertEqual(len(output), 64)
            self.assertTrue(all(c in '0123456789abcdef' for c in output))

    def test_hash_helper_file_not_found(self):
        """--hash con archivo inexistente → exit 1."""
        nonexistent = '/nonexistent/file/path.py'
        real_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            rc = vc.main(['prog', '--hash', nonexistent])
        finally:
            sys.stdout = real_stdout

        self.assertEqual(rc, 1)

    def test_hash_helper_matches_validation(self):
        """Hash impreso por --hash coincide con el que acepta la validación."""
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)

            test_content = 'import unittest\nclass TestHello(unittest.TestCase): pass\n'
            test_file = os.path.join(repo_root, 'tests', 'test_sample.py')
            _write(repo_root, 'tests/test_sample.py', test_content)

            # Obtener hash con el helper
            real_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                rc = vc.main(['prog', '--hash', test_file])
                helper_hash = sys.stdout.getvalue().strip()
            finally:
                sys.stdout = real_stdout

            self.assertEqual(rc, 0)

            # Crear contrato con ese hash
            contract_with_hash = VALID_CONTRACT.replace(
                'tests_sha256: "c11c4064b2030dac8352c6453a128af2aedcb3ecc711aed805f22768cf54fda4"',
                f'tests_sha256: "{helper_hash}"'
            )
            _write(repo_root, 'knowledge/contracts/c.md', contract_with_hash)
            _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')

            # Validar: debe pasar sin errores
            findings = vc.validate_directory(contracts_dir, repo_root=repo_root)
            errors = [f for f in findings if f.level == 'ERROR']
            self.assertEqual(errors, [], msg=[str(f) for f in findings])


class TestExitCode(unittest.TestCase):
    def _run_main(self, content, create_files=True):
        with tempfile.TemporaryDirectory() as repo_root:
            contracts_dir = os.path.join(repo_root, 'knowledge', 'contracts')
            os.makedirs(contracts_dir, exist_ok=True)
            _write(repo_root, 'knowledge/contracts/c.md', content)
            if create_files:
                _write(repo_root, 'src/hello.py', 'def hello(name: str) -> str:\n    return f"Hello, {name}"\n')
                _write(repo_root, 'tests/test_sample.py', 'import unittest\nclass TestHello(unittest.TestCase): pass\n')
            real = sys.stdout
            sys.stdout = StringIO()
            try:
                rc = vc.main(['prog', '--repo-root', repo_root, contracts_dir])
            finally:
                sys.stdout = real
            return rc

    def test_exit_code_zero_when_only_warnings(self):
        bad = VALID_CONTRACT.replace("forbids: ['network', 'subprocess']\n", '')
        self.assertEqual(self._run_main(bad), 0)

    def test_exit_code_one_when_error(self):
        bad = VALID_CONTRACT.replace("type: 'Task Contract'", "type: 'X'")
        self.assertEqual(self._run_main(bad), 1)


if __name__ == '__main__':
    unittest.main()