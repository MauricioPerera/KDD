---
type: 'Task Contract'
title: 'Enforcement determinista de budgets'
description: 'Comprueba que los targets Python respetan los límites de complejidad declarados por sus contratos.'
tags: ['ccdd', 'budget', 'quality']
task: budget-enforcement
intent: 'Hace cumplir los budgets de complejidad declarados.'
target: scripts/validate_budgets.py
signature: 'def validate_directory(contracts_dir: str, repo_root: str, contract_name: str | None = None) -> list:'
test_command: 'python -m unittest tests/test_validate_budgets.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 180
  params_max: 3
tests: 'tests/test_validate_budgets.py'
tests_sha256: 'e153bccbf6c000edb7e1607759d245315e8a91cc1ab73e3c28290f176457518a'
touch_only: ['scripts/validate_budgets.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

El gate convierte los límites de complejidad de cada contrato en una comprobación
ejecutable y reproducible. Solo afirma métricas para targets Python; otros lenguajes
se omiten explícitamente hasta tener un medidor equivalente.

## Interface

```python
def validate_directory(contracts_dir: str, repo_root: str, contract_name: str | None = None) -> list:
    """Return deterministic findings for Python targets over their budgets."""
```

## Invariants

- Un exceso de complejidad, anidamiento, líneas o parámetros produce exit code 1.
- Un target no Python no se presenta como validado: se omite por alcance declarado.
- El gate no usa red, subprocess ni un modelo de lenguaje.
- Los contratos se recorren en orden estable y pueden limitarse a uno con `--contract`.

## Examples

- Un target bajo todos sus límites produce `OK` y exit code 0.
- Un target que supera `cyclomatic_max` produce `BUDGET_CYCLOMATIC` y exit code 1.
- Un target TypeScript se omite porque este gate solo mide Python.

## Do / Don't

- DO: usar el mismo nombre canónico de budget que el validador de contratos.
- DO: añadir un medidor específico antes de afirmar enforcement para otro lenguaje.
- DON'T: reemplazar la revisión del contrato por una métrica aislada.

## Tests

El oráculo congelado está en `tests/test_validate_budgets.py` y cubre límites,
excesos de complejidad y parámetros, y targets de otros lenguajes.

## Constraints

- PARAR y reportar si un target Python no se puede analizar con `ast`.
- Este gate no cambia los límites existentes; solo hace ejecutables los declarados.
- La ejecución global es diagnóstica hasta migrar los budgets históricos; el enforcement
  de una tarea nueva o modificada debe usar `--contract <task>`.
