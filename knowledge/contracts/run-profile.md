---
type: 'Task Contract'
title: 'Perfiles de validación KDD'
description: 'Ejecuta una secuencia determinista de gates según el nivel de adopción elegido.'
tags: ['kdd', 'adopcion', 'tooling']
task: run-profile
intent: 'Ejecuta un perfil progresivo de validación.'
target: scripts/run_profile.py
signature: 'def run_profile(name: str, repo_root: str, runner=None) -> dict:'
test_command: 'python -m unittest tests/test_run_profile.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
  lines_max: 140
  params_max: 3
tests: 'tests/test_run_profile.py'
tests_sha256: 'a29e2aaa83a85f8da3ad133d9d1d3b859269bf6bfc5c07396a18f0af4db7d6dc'
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
def run_profile(name: str, repo_root: str, runner=None) -> dict:
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

## Do / Don't

- DO: comenzar proyectos nuevos con `minimal` y subir a `standard` cuando el contrato base esté estable.
- DO: usar `strict` antes de una entrega o en CI de proyectos maduros.
- DON'T: interpretar `minimal` como ausencia de tests; siempre ejecuta la suite del proyecto.

## Tests

El oráculo congelado está en `tests/test_run_profile.py` y verifica orden,
composición, rechazo de perfiles desconocidos y parada ante fallos.

## Constraints

- PARAR y reportar si un perfil necesita un comando no disponible en el entorno.
- Este contrato no autoriza a modificar los gates individuales ni sus oráculos.
