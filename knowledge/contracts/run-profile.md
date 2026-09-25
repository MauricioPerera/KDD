---
type: 'Task Contract'
title: 'Perfiles de validación KDD'
description: 'Ejecuta una secuencia determinista de gates según el nivel de adopción elegido.'
tags: ['kdd', 'adopcion', 'tooling']
task: run-profile
intent: 'Ejecuta perfiles progresivos; standard/strict exigen oráculos aprobados y todos los test_command.'
target: scripts/run_profile.py
signature: 'def run_profile(name: str, repo_root: str, mutation_contract: str | None = None, budget_contract: str | None = None, runner=None, approved_ref: str | None = None) -> dict:'
test_command: 'python -m unittest tests/test_run_profile.py'
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 140
  params_max: 6
tests: 'tests/test_run_profile.py'
tests_sha256: 'b905c72031c536b2b0601b4b91244e08a3728bf46a4f8fe9e0579d10cc0cad88'
touch_only: ['scripts/run_profile.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

El perfil permite que un proyecto adopte KDD por etapas sin perder comandos
reproducibles. `minimal` ofrece una entrada pequeña; `standard` es la ruta
recomendada; `strict` añade diagnósticos profundos y auditorías.

## Interface

```python
def run_profile(name: str, repo_root: str, mutation_contract: str | None = None, budget_contract: str | None = None, runner=None, approved_ref: str | None = None) -> dict:
    """Run profile steps and stop at the first non-zero result."""
```

## Invariants

- Los perfiles son inclusivos en cobertura: `standard` contiene los gates de
  `minimal` y `strict` contiene los de `standard`. `standard` intercala el
  baseline aprobado antes de la suite, por lo que `minimal` no es prefijo
  literal de `standard`.
- El orden de comandos es estable y no usa shell.
- Un fallo detiene el perfil y nombra el paso que falló.
- `standard` y `strict` requieren `approved_ref` como SHA completo de un commit;
  el gate compara todos los contratos y oráculos antes de ejecutar la suite
  heredada o los `test_command`.
- `contract_tests` ejecuta todos los `test_command` de los contratos, incluidos
  los del producto; un fallo del producto hace fallar el perfil.
- El resultado distingue PASS, FAIL y SKIP; un gate opcional sin datos no cuenta
  como PASS. El reporte de contratos separa producto e infraestructura.
- Un perfil desconocido produce `ValueError`.

## Examples

- `minimal` ejecuta contratos y la suite del proyecto una sola vez.
- `standard` añade referencia aprobada, test_command de cada contrato, specs,
  OKF, ASCII, rules, skills, changelog y secretos.
- `strict` añade budgets, seals, forbids y preflight.
- `strict --mutation-contract <ruta>` añade mutación controlada de una tarea concreta.
- `strict --budget-contract <ruta>` reemplaza el diagnóstico global por enforcement de una tarea concreta.

## Do / Don't

- DO: comenzar proyectos nuevos con `minimal` y subir a `standard` cuando el contrato base esté estable.
- DO: usar `strict` antes de una entrega o en CI de proyectos maduros.
- DON'T: interpretar `minimal` como ausencia de tests; siempre ejecuta la suite del proyecto.
- DON'T: activar mutación sin indicar un contrato concreto.
- DON'T: interpretar el diagnóstico global de budgets históricos como enforcement de una tarea nueva.

## Tests

El oráculo congelado está en `tests/test_run_profile.py` y verifica orden,
referencia obligatoria, ejecución de tests de contratos, SKIP y parada ante fallos.

## Constraints

- PARAR y reportar si un perfil necesita un comando no disponible en el entorno.
- Los cambios del gate de test_command y de baseline están regidos por sus
  respectivos contratos.
