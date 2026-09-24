---
type: 'Task Contract'
title: 'Perfiles de validación KDD'
description: 'Ejecuta una secuencia determinista de gates según el nivel de adopción elegido.'
tags: ['kdd', 'adopcion', 'tooling']
task: run-profile
intent: 'Ejecuta un perfil progresivo de validación.'
target: scripts/run_profile.py
signature: 'def run_profile(name: str, repo_root: str, mutation_contract: str | None = None, budget_contract: str | None = None, runner=None) -> dict:'
test_command: 'python -m unittest tests/test_run_profile.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
  lines_max: 140
  params_max: 3
tests: 'tests/test_run_profile.py'
tests_sha256: 'c1d1794f02df5aca815e51f7c3c52667af45c52f494f0b41846c667cb3e57ee0'
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
def run_profile(name: str, repo_root: str, mutation_contract: str | None = None, budget_contract: str | None = None, runner=None) -> dict:
    """Run profile steps and stop at the first non-zero result."""
```

## Invariants

- Los perfiles son inclusivos: `minimal` es prefijo de `standard`, y `standard` de `strict`.
- El orden de comandos es estable y no usa shell.
- Un fallo detiene el perfil y nombra el paso que falló.
- Un perfil desconocido produce `ValueError`.

## Examples

- `minimal` ejecuta contratos y la suite del proyecto una sola vez.
- `standard` añade specs, OKF, ASCII, rules, skills, changelog y secretos.
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
composición, rechazo de perfiles desconocidos y parada ante fallos.

## Constraints

- PARAR y reportar si un perfil necesita un comando no disponible en el entorno.
- Este contrato no autoriza a modificar los gates individuales ni sus oráculos.
