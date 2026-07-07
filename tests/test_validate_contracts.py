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

    def test_sha256_absent_warning(self):
        """(c) clave ausente → WARNING FM_TESTS_FROZEN (recomendada)"""
        # VALID_CONTRACT ya no tiene tests_sha256
        findings = self._run(VALID_CONTRACT)
        warnings = [f for f in findings if f.level == 'WARNING']
        fm_tests_frozen_warnings = [f for f in warnings if f.rule == 'FM_TESTS_FROZEN']
        self.assertTrue(len(fm_tests_frozen_warnings) >= 1, msg=[str(f) for f in findings])
        self.assertIn('recomendada', fm_tests_frozen_warnings[0].message)

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
        self.assertIn('formato inválido', fm_tests_frozen_errors[0].message)

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