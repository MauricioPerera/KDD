---
type: 'Task Contract'
title: 'Arranque guiado de un proyecto KDD'
description: 'Compone la inicialización de la plantilla con un archivo de primeros pasos adaptado al perfil elegido.'
tags: ['kdd', 'init', 'adopcion']
task: bootstrap-project
intent: 'Prepara un proyecto KDD con una guía inicial.'
target: scripts/bootstrap_project.py
signature: 'def bootstrap_project(repo_dir: str, apply: bool, name: str, profile: str = "standard", repository: str = None) -> dict:'
test_command: 'python -m unittest tests/test_bootstrap_project.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
  lines_max: 150
  params_max: 5
tests: 'tests/test_bootstrap_project.py'
tests_sha256: '4d8b41fbea20593519acc1a74460abfa1c1d9d0e7226c489190ae72015728bfb'
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
                      profile: str = "standard", repository: str = None) -> dict:
    """Initialize and optionally write the human-friendly start guide."""
```

CLI: `python scripts/bootstrap_project.py [--apply --repository OWNER/REPO]
[--name <proyecto>] [--profile minimal|standard|strict] [--repo-dir .]`.
`repository` se agrega al final para conservar los argumentos posicionales
existentes. Dry-run sin identidad sigue permitido; apply exige OWNER/REPO.

## Invariants

- Sin `--apply` no se escribe `KDD-START-HERE.md`.
- El wrapper delega la limpieza a `init_project`; no duplica su manifiesto.
- La identidad explicita se transmite sin reemplazarla ni inferirla del entorno.
  La politica de completion generada pertenece al OWNER/REPO recibido.
- Apply sin identidad, con identidad invalida o con manifiesto incompleto
  termina con exit 2, conserva la copia y no genera la guia.
- El perfil solo puede ser `minimal`, `standard` o `strict`.
- La guía declara que los gates no sustituyen el juicio de producto humano.
- La guia explica la politica quality/product.json y ambas variables de
  aprobacion del [CI nuevo](./bootstrap-product-quality-ci.md), tambien en
  minimal. El comando local minimal conserva su interfaz sin --approved-ref.
  La adaptacion del workflow la realiza init_project, no el wrapper.

## Examples

- Dry-run minimal calcula el plan y no crea archivos.
- Apply standard crea `KDD-START-HERE.md` con el comando del perfil standard,
  incluyendo la referencia aprobada obligatoria.
- El perfil minimal no exige `--approved-ref`.
- Un perfil desconocido produce `ValueError` sin escribir la guía.
- Apply con `--repository ExampleCo/Shop` crea una politica para ExampleCo/Shop.

## Do / Don't

- DO: empezar con `minimal` en proyectos pequeños y subir de perfil gradualmente.
- DO: conservar la guía como orientación, no como sustituto del contrato de tarea.
- DON'T: ejecutar el apply sobre un repositorio que no sea una copia controlada de la plantilla.

## Tests

El oráculo congelado está en `tests/test_bootstrap_project.py` y verifica dry-run,
composición con el inicializador, guía generada y perfiles inválidos.
La [integracion de proyecto nuevo](./project-initialization.md) ejercita la
API y CLI contra el inicializador real, sin sustituirlo por mocks.

## Constraints

- PARAR y reportar si `init_project` rechaza el manifiesto incompleto.
- Este wrapper no ejecuta comandos de validación ni modifica archivos fuera de su guía.
