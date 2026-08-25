# fix/path-anchoring — REPORT

Defensa en profundidad contra path-traversal en los 3 scripts sellados. Un
campo externo (`task`/`tests`/`target`) se unía con `os.path.join(repo_root,
campo)` y se leía/escribía/hasheaba **sin anclar el resultado dentro del
subdirectorio esperado**. Ahora, cualquier path construido desde un campo
externo se verifica con `os.path.realpath` + `os.path.commonpath` contra el
árbol esperado antes de cualquier I/O; si escapa, se reporta como error de
validación con mensaje claro (no crash, no lectura/escritura fuera del árbol).

Archivos tocados (cada uno dentro del `touch_only` de su propio contrato):
- `scripts/export_gate_contract.py` (contrato `export-gate-contract.md`)
- `scripts/validate_attestation.py` (contrato `attestation-gate.md`)
- `scripts/preflight.py` (contrato `preflight.md`)

Helper común añadido en los 3 (`_within(path, base)`): `True` si `realpath(path)`
cae dentro de `realpath(base)`; `ValueError` (unidades distintas en Windows)
cuenta como fuera. Función pura (sin I/O, sin entorno).

## Cambios

### `scripts/export_gate_contract.py`
- Anclaje de la ruta de salida `out_path = os.path.join(out_dir_abs,
  task_ascii + ".gate.md")` dentro de `out_dir_abs`. Si `task` (campo del
  contrato) resuelve fuera del out-dir → `ValueError` ("contrato invalido",
  CLI exit 2). No se escribe fuera del árbol.

### `scripts/validate_attestation.py`
- Anclaje de `contract_path = os.path.join(contracts_dir, data['task'] +
  '.md')` dentro de `knowledge/contracts`. Si escapa → finding
  `CONTRACT_MISSING` con mensaje que indica el escape (no se lee fuera del
  árbol). Reutiliza la regla `CONTRACT_MISSING` (no se agregan reglas nuevas
  al oraculo).
- El `open(contract_path)` (línea ~169 original) ahora está envuelto en
  `try/except OSError` → finding `CONTRACT_MISSING` ("no se pudo leer el
  contrato") en vez de propagar la excepción y crashear `validate_report` /
  `validate_directory`.

### `scripts/preflight.py`
- Anclaje de `tests_path = os.path.join(repo_root, tests_rel)` dentro de
  `repo_root` en `_check_seal`, antes de `os.path.isfile` / lectura / hash.
  Si escapa → `_result(1, stderr='tests path escapes repo_root: ...')` (FAIL
  del chequeo seal, no crash, no lectura fuera del repo).

## HECHOS 1-4: suites selladas y preflight

### Baseline (antes de los fixes)
```
$ python -m unittest tests/test_export_gate_contract.py tests/test_validate_attestation.py tests/test_preflight.py
..................................................................
----------------------------------------------------------------------
Ran 66 tests in 1.234s

OK

$ python scripts/preflight.py ; echo "EXIT=$?"
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
EXIT=0
```

### HECHO 1 — `tests/test_export_gate_contract.py` (sin modificar el test)
```
$ python -m unittest tests/test_export_gate_contract.py -v
...
----------------------------------------------------------------------
Ran 27 tests in 0.746s

OK
```

### HECHO 2 — `tests/test_validate_attestation.py` (sin modificar el test)
```
$ python -m unittest tests/test_validate_attestation.py -v
----------------------------------------------------------------------
Ran 22 tests in 0.083s

OK
```

### HECHO 3 — `tests/test_preflight.py` (sin modificar el test)
```
$ python -m unittest tests/test_preflight.py -v
...
----------------------------------------------------------------------
Ran 17 tests in 0.365s

OK
```

### HECHO 4 — `python scripts/preflight.py` (mismo resultado que al arrancar)
```
$ python scripts/preflight.py ; echo "EXIT=$?"
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
EXIT=0
```
Idéntico a la baseline (19/19, EXIT=0).

## HECHO 5 — Evidencia de rechazo de `../algo` (ejecutada a mano)

Script de evidencia: `scratchpad/evidence.py` (ejercita los 3 scripts en
tmpdirs aislados; NO toca los tests sellados ni los contratos). Salida real:

```
======================================================================
1) export_gate_contract.py  |  task: "../../escape"
======================================================================
OK ValueError (contrato invalido): la clave 'task' resuelve a una ruta fuera del out-dir: '../../escape'
¿Se creo archivo fuera del arbol (tmp/escape.gate.md)? -> False
¿out_dir existe? -> True

======================================================================
2) validate_attestation.py  |  task: "../SECRET"  (sin comillas)
======================================================================
ERROR [CONTRACT_MISSING] x-REPORT.md: task resuelve a una ruta fuera de knowledge/contracts: '../SECRET'
ERROR [TASK_MISMATCH] x-REPORT.md: task='../SECRET' no coincide con el nombre de archivo 'x'
rules = ['CONTRACT_MISSING', 'TASK_MISMATCH']
¿Aparece CONTRACT_HASH_MISMATCH (leerio el secreto y comparo)? -> False
¿Aparece CONTRACT_MISSING (rechazo claro, sin leer)? -> True
¿El mensaje de CONTRACT_MISSING indica el escape? -> True

======================================================================
3) preflight.py  |  tests: "../../../etc/passwd"
======================================================================
overall_ok = False
frontmatter: PASS
seal: FAIL
test_command: FAIL
Summary: 1/3
seal stderr: tests path escapes repo_root: ../OUTSIDE.txt
¿seal FAIL por escape (no por mismatch/hash)? -> True
¿Se hasheo el archivo fuera (mismatch en vez de escape)? -> False

======================================================================
4) validate_attestation.py  |  open(contract) lanza OSError
======================================================================
validate_report no crasheo. rules = ['CONTRACT_MISSING']
¿CONTRACT_MISSING por OSError de lectura? -> True
validate_directory no crasheo. #findings = 1

=== EVIDENCIA COMPLETA ===
```

### Lectura de la evidencia
1. **export_gate_contract.py**: `task: "../../escape"` → `ValueError` claro;
   no se crea archivo fuera del árbol (`tmp/escape.gate.md` = False).
2. **validate_attestation.py**: `task: "../SECRET"` apuntaba a un archivo
   "secreto" (`tmp/knowledge/SECRET.md`, dentro de `repo_root` pero fuera de
   `knowledge/contracts`) cuyo hash se declaró **coincidente** con
   `contract_sha256`. Sin el fix el gate lo leería, el hash coincidiría y lo
   aceptaría silenciosamente (el bug). Con el fix → `CONTRACT_MISSING` con
   mensaje de escape, **sin** `CONTRACT_HASH_MISMATCH` (no se leyó).
3. **preflight.py**: `tests: "../OUTSIDE.txt"` → seal FAIL con
   `tests path escapes repo_root` (no `seal mismatch`: no se hasheó el archivo
   fuera del repo).
4. **OSError**: `open(contract_path)` forzado a lanzar `OSError` →
   `validate_report` y `validate_directory` devuelven un finding
   `CONTRACT_MISSING` en vez de propagar la excepción (no crashea).

## Alcance del diff
```
$ git diff --stat
 scripts/export_gate_contract.py | 24 ++++++++++++++++++
 scripts/preflight.py            | 23 ++++++++++++++++++
 scripts/validate_attestation.py | 54 +++++++++++++++++++++++++++++++++--------
 3 files changed, 91 insertions(+), 10 deletions(-)
```
Solo los 3 scripts. Tests sellados (`tests/test_*.py`) y contratos
(`knowledge/contracts/*.md`) **sin modificar**.