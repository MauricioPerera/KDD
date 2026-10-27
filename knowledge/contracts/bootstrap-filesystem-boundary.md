---
type: 'Task Contract'
title: 'Confinar rutas fisicas del bootstrap'
description: 'Rechazar alias peligrosos antes de escribir o borrar archivos de una copia de proyecto.'
tags: ['bootstrap', 'security', 'filesystem', 'integration']
task: bootstrap-filesystem-boundary
intent: 'Mantener todos los efectos del inicializador dentro de la raiz fisica elegida.'
target: scripts/init_project.py
language: python
signature: 'def init_project(repo_dir, apply, name, repository=None) -> dict:'
test_command: 'python -m unittest tests/test_bootstrap_boundary.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 120
  params_max: 5
tests: tests/test_bootstrap_boundary.py
tests_sha256: '2851ca19f984aa58157b9c58b70c1ff84bad795ec660645ef26b3c138482242a'
touch_only: ['scripts/init_project.py', 'scripts/bootstrap_project.py', 'scripts/bootstrap_transaction.py']
deps_allowed: ['stdlib', 'bootstrap_transaction']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Aplicar el [protocolo de seguridad y recuperacion](../bootstrap-safety.md)
al [inicializador](init-project.md) y [arranque guiado](bootstrap-project.md).

## Interface

Las APIs y CLI publicas se conservan. El helper de transaccion valida todas
las rutas gestionadas, ancestros, tipos y numero de hardlinks antes del primer
borrado. Alias de la raiz explicita permitido; alias bajo esa raiz rechazado.
Error de perimetro: ValueError con codigo BOOTSTRAP_PATH; CLI termina no cero.

## Invariants

Ningun canario externo cambia ni desaparece. Se rechazan symlinks, junctions,
reparse points y archivos de multiples hardlinks del plan. Validacion tambien
en dry-run. Se conservan enlaces/archivos ajenos al plan. No reemplazar el
manifiesto explicito por un glob ni tocar producto/tareas propias.

## Examples

- src enlazado externamente: abortar antes de unlink.
- workflow o README enlazado: abortar antes de reescribir.
- guia hardlink: no truncar su otro nombre externo.
- copia ordinaria o alias explicito de raiz: inicializar normalmente.

## Do / Don't

- DO: usar enlaces nativos y comparar snapshots/canarios completos.
- DON'T: considerar suficiente is_symlink o resolve sin comprobar hardlinks.

## Tests
La [preparacion de fixtures](fixture-preparation-cost.md) conserva enlaces reales
y todas las aserciones; no usa un proceso auxiliar por junction.

tests/test_bootstrap_boundary.py incluye el fixture real compartido y los
controles de ambas entradas. Windows: junctions; Ubuntu: symlinks; hardlinks en
ambos. No reemplaza IO ni validadores por mocks y no omite casos de main.

## Constraints

Solo stdlib en la implementacion. Baseline revisado antes de implementar.
PARAR y reportar si hace falta cambiar un oraculo anterior, runtime o proteccion.
