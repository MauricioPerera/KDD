---
type: 'Task Contract'
title: 'Arranque guiado de un proyecto KDD'
description: 'Compone la inicialización de la plantilla con un archivo de primeros pasos adaptado al perfil elegido.'
tags: ['kdd', 'init', 'adopcion']
task: bootstrap-project
intent: 'Prepara un proyecto KDD con una guía inicial.'
target: scripts/bootstrap_project.py
signature: 'def bootstrap_project(repo_dir: str, apply: bool, name: str, profile: str = "standard") -> dict:'
test_command: 'python -m unittest tests/test_bootstrap_project.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
  lines_max: 150
  params_max: 4
tests: 'tests/test_bootstrap_project.py'
tests_sha256: '90e10c2b49edc4a698a0515a807de69fef116216aa467af69533b341e08f7b2b'
touch_only: ['scripts/bootstrap_project.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

El inicializador histórico limpia los ejemplos, pero deja al equipo decidir qué
hacer después. Este wrapper conserva su dry-run y su manifiesto explícito, y añade
una guía `KDD-START-HERE.md` con el perfil y los comandos de continuación.

## Interface

```python
def bootstrap_project(repo_dir: str, apply: bool, name: str,
                      profile: str = "standard") -> dict:
    """Initialize and optionally write the human-friendly start guide."""
```

## Invariants

- Sin `--apply` no se escribe `KDD-START-HERE.md`.
- El wrapper delega la limpieza a `init_project`; no duplica su manifiesto.
- El perfil solo puede ser `minimal`, `standard` o `strict`.
- La guía declara que los gates no sustituyen el juicio de producto humano.

## Examples

- Dry-run minimal calcula el plan y no crea archivos.
- Apply standard crea `KDD-START-HERE.md` con el comando del perfil standard,
  incluyendo la referencia aprobada obligatoria.
- El perfil minimal no exige `--approved-ref`.
- Un perfil desconocido produce `ValueError` sin escribir la guía.

## Do / Don't

- DO: empezar con `minimal` en proyectos pequeños y subir de perfil gradualmente.
- DO: conservar la guía como orientación, no como sustituto del contrato de tarea.
- DON'T: ejecutar el apply sobre un repositorio que no sea una copia controlada de la plantilla.

## Tests

El oráculo congelado está en `tests/test_bootstrap_project.py` y verifica dry-run,
composición con el inicializador, guía generada y perfiles inválidos.

## Constraints

- PARAR y reportar si `init_project` rechaza el manifiesto incompleto.
- Este wrapper no ejecuta comandos de validación ni modifica archivos fuera de su guía.
