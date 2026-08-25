# fix-findings-json-load — REPORT

## Bug

Los 6 validadores de findings de Capa 3 hacían `json.load(fh)` sobre
`<scan_dir>/findings.json` sin try/except. El docstring de cada módulo promete
exit code 2 si el archivo "existe pero está corrupto/mal formado", pero un JSON
inválido (`json.JSONDecodeError`, que hereda de `ValueError`) no estaba atrapado:
el script crasheaba con traceback y salía con exit 1 (excepción no manejada),
no con el exit 2 documentado.

## Fix

En cada uno de los 6 scripts se envolvió la lectura+parseo del `findings.json`
en un `try/except json.JSONDecodeError` que emite un mensaje `ERROR [PARSE_ERROR]`
a stderr (mismo formato/clareza que los otros exit-2 existentes, ej.
`ERROR [DOCUMENT_TYPE]`) y retorna `2`. El caso feliz (JSON válido) no cambia:
el parseo exitoso cae al flujo existente sin alteración.

Archivos modificados (solo estos 6, idéntico patrón):

- scripts/validate_security_findings.py
- scripts/validate_privacy_findings.py
- scripts/validate_accessibility_findings.py
- scripts/validate_compliance_findings.py
- scripts/validate_observability_findings.py
- scripts/validate_test_coverage_findings.py

Patón aplicado en cada uno (bloque que reemplaza al `with open(...) as fh:
findings_doc = json.load(fh)` suelto):

```python
    try:
        with open(findings_path, "r", encoding="utf-8") as fh:
            findings_doc = json.load(fh)
    except json.JSONDecodeError as exc:
        print(
            f"ERROR [PARSE_ERROR] {findings_path}: JSON invalido/corrupto -- "
            f"no se pudo parsear el artefacto sellado ({exc})",
            file=sys.stderr,
        )
        return 2
```

## Tests

Se crearon los 6 archivos de tests (no existían): cada uno escribe un
`findings.json` con JSON inválido (`{invalid`) y con texto no-JSON, y verifica
exit code 2 + mensaje `PARSE_ERROR`; más un test de path inexistente que sigue
dando exit 0 (capa opcional).

- tests/test_validate_security_findings.py
- tests/test_validate_privacy_findings.py
- tests/test_validate_accessibility_findings.py
- tests/test_validate_compliance_findings.py
- tests/test_validate_observability_findings.py
- tests/test_validate_test_coverage_findings.py

---

## Salida REAL de los 3 comandos del HECHO

### CMD 1 — `python -m unittest discover -s tests -p "test_validate_*findings*.py" -v`

```
test_json_invalido_da_exit_2 (test_validate_accessibility_findings.TestCorruptFindings.test_json_invalido_da_exit_2) ... ok
test_path_inexistente_da_exit_0 (test_validate_accessibility_findings.TestCorruptFindings.test_path_inexistente_da_exit_0) ... ok
test_texto_no_json_da_exit_2 (test_validate_accessibility_findings.TestCorruptFindings.test_texto_no_json_da_exit_2) ... ok
test_json_invalido_da_exit_2 (test_validate_compliance_findings.TestCorruptFindings.test_json_invalido_da_exit_2) ... ok
test_path_inexistente_da_exit_0 (test_validate_compliance_findings.TestCorruptFindings.test_path_inexistente_da_exit_0) ... ok
test_texto_no_json_da_exit_2 (test_validate_compliance_findings.TestCorruptFindings.test_texto_no_json_da_exit_2) ... ok
test_json_invalido_da_exit_2 (test_validate_observability_findings.TestCorruptFindings.test_json_invalido_da_exit_2) ... ok
test_path_inexistente_da_exit_0 (test_validate_observability_findings.TestCorruptFindings.test_path_inexistente_da_exit_0) ... ok
test_texto_no_json_da_exit_2 (test_validate_observability_findings.TestCorruptFindings.test_texto_no_json_da_exit_2) ... ok
test_json_invalido_da_exit_2 (test_validate_privacy_findings.TestCorruptFindings.test_json_invalido_da_exit_2) ... ok
test_path_inexistente_da_exit_0 (test_validate_privacy_findings.TestCorruptFindings.test_path_inexistente_da_exit_0) ... ok
test_texto_no_json_da_exit_2 (test_validate_privacy_findings.TestCorruptFindings.test_texto_no_json_da_exit_2) ... ok
test_json_invalido_da_exit_2 (test_validate_security_findings.TestCorruptFindings.test_json_invalido_da_exit_2) ... ok
test_path_inexistente_da_exit_0 (test_validate_security_findings.TestCorruptFindings.test_path_inexistente_da_exit_0) ... ok
test_texto_no_json_da_exit_2 (test_validate_security_findings.TestCorruptFindings.test_texto_no_json_da_exit_2) ... ok
test_json_invalido_da_exit_2 (test_validate_test_coverage_findings.TestCorruptFindings.test_json_invalido_da_exit_2) ... ok
test_path_inexistente_da_exit_0 (test_validate_test_coverage_findings.TestCorruptFindings.test_path_inexistente_da_exit_0) ... ok
test_texto_no_json_da_exit_2 (test_validate_test_coverage_findings.TestCorruptFindings.test_texto_no_json_da_exit_2) ... ok

----------------------------------------------------------------------
Ran 18 tests in 0.054s

OK
```

### CMD 2 — `python -m unittest discover -s tests -p "test_*.py"`

```
Ran 740 tests in 23.767s

OK
```

(Exit 0. La línea `ERROR: no se pudo leer does-not-exist.diff` que aparece en
el output es stdout esperado de un test de fixture de error, no un fallo de
unittest — el resumen dice `OK` y el exit code es 0.)

### CMD 3 — `python scripts/preflight.py`

```
validate_contracts: PASS
validate_specs: PASS
validate_okf: PASS
lint_ascii: PASS
validate_rules: PASS
validate_skills: PASS
validate_changelog: PASS
validate_ux_page: PASS
validate_diagrams: PASS
validate_security_findings: PASS
validate_compliance_findings: PASS
validate_privacy_findings: PASS
validate_accessibility_findings: PASS
validate_dependency_eol_findings: PASS
validate_observability_findings: PASS
validate_test_coverage_findings: PASS
validate_test_commands: PASS
scan_secrets: PASS
validate_attestation: PASS
Summary: 19/19
```

Idéntico al resultado al arrancar (19/19 PASS, exit 0).