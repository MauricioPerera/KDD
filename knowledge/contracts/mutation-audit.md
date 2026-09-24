---
type: 'Task Contract'
title: 'Auditor determinista de mutación'
description: 'Ataca targets Python con mutaciones sintácticas controladas y clasifica la respuesta del oráculo congelado.'
tags: ['ccdd', 'oraculo', 'mutation']
task: mutation-audit
intent: 'Ataca un target Python con mutaciones controladas.'
target: scripts/mutation_audit.py
signature: 'def audit_contract(contract_path: str, repo_root: str, timeout: int = 120) -> dict:'
test_command: 'python -m unittest tests/test_mutation_audit.py'
budget:
  cyclomatic_max: 14
  nesting_max: 5
  lines_max: 220
  params_max: 3
tests: 'tests/test_mutation_audit.py'
tests_sha256: '76279f6f9e1adb1aaa36b791488f89943b6852a5340c7c7577681011fde63410'
touch_only: ['scripts/mutation_audit.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

El sello `tests_sha256` demuestra que el oráculo no cambió, pero no demuestra que
pueda detectar defectos. Este auditor crea mutantes Python en una copia temporal,
ejecuta el `test_command` y conserva una clasificación explícita de la evidencia.

## Interface

```python
def audit_contract(contract_path: str, repo_root: str, timeout: int = 120) -> dict:
    """Classify controlled mutants as DETECTED, SURVIVED or INCONCLUSIVE."""
```

## Invariants

- Nunca modifica el working tree ni el índice del repositorio real.
- `DETECTED` significa que el test_command terminó con código distinto de cero.
- `SURVIVED` significa que el mutante pasó; en `--strict` el comando falla.
- `INCONCLUSIVE` significa timeout y nunca se presenta como mutación detectada.
- Targets no Python se omiten explícitamente.

## Examples

- Invertir una comparación que el test cubre produce `DETECTED`.
- Un mutante que conserva el exit code cero produce `SURVIVED`.
- Un test que supera el timeout produce `INCONCLUSIVE`, no `DETECTED`.

## Do / Don't

- DO: ejecutar el auditor sobre un contrato concreto en una copia aislada.
- DO: conservar la tabla de operadores y estados como evidencia.
- DON'T: re-sellar tests para hacer desaparecer un mutante superviviente.

## Tests

El oráculo congelado está en `tests/test_mutation_audit.py` y cubre generación,
detección real y omisión explícita de targets no Python.

## Constraints

- PARAR y reportar si el test_command requiere red o efectos externos.
- Este auditor no afirma cobertura de lenguajes que no soporta.
