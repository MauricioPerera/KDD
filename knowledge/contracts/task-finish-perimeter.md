---
type: 'Task Contract'
title: 'Perimetro obligatorio antes de cerrar una tarea'
description: 'Bloquear finish antes del oraculo si la implementacion o su integracion exceden el permiso aprobado.'
tags: ['tasks', 'git', 'perimeter', 'integration']
task: task-finish-perimeter
intent: 'Exigir el perimetro aprobado al cerrar una tarea.'
target: scripts/task_git.py
signature: 'def mutate(repo_root, operation, task_id, options) -> dict:'
test_command: 'python -m unittest tests.test_task_finish_perimeter'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_task_finish_perimeter.py
tests_sha256: '42bfaee9f4675225cbc8c243994b887587a29fc7bdd1c7f26c0e55d1c799a8dd'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts', 'validate_tasks']
forbids: ['network', 'llm']
---

## Intent

Cerrar KG-1 del [objetivo de gobierno](../kdd-governance-closure.md) en el
[coordinador canonico](task-journal.md). La atribucion, el recibo y las
responsabilidades se definen una sola vez en ese objetivo.

## Interface

Conservar mutate y las interfaces publicas del
[diario](task-git-complexity.md). El verificador compartido de alcance vive
en task_git.py, dentro del bundle confiable existente; el validador historico
debe poder usarlo sin ejecutar codigo del producto.

## Invariants

- Rechazar TASK_PERIMETER antes del oraculo ante un cambio no autorizado,
  nombrando todas las rutas infractoras, sin publicar estado ni evidencia.
- Tomar permisos del contrato aprobado y cambios de los objetos Git atribuidos
  a la tarea; incluir historia revertida y aporte de integracion.
- Conservar cambios ajenos de main y resoluciones permitidas del merge.
- Agregar el recibo perimeter definido en el nodo canonico, sin alterar Task v1.
- Mantener hashes, identidad, locks, fronteras de rutas, rollback, firmas y
  los presupuestos mas estrictos existentes de todo task_git.py.

## Examples

- Solo src/feature1.py autorizado, implementacion valida -> done con recibo.
- Se agrega src/outside.py o el merge agrega merge-only.txt -> TASK_PERIMETER,
  sin ejecutar el oraculo ni cambiar HEAD, indice, ramas o tareas.
- Se cambia fuera de alcance y luego se revierte -> rechazo por historia real.

## Do / Don't

- DO reutilizar la semantica de [touch_only](perimeter-gate.md) y conservar la
  aprobacion independiente de [calidad](../quality-approval.md).
- DON'T ampliar permisos desde el candidato, exceptuar directorios completos
  o atribuir a esta tarea todo el avance ajeno de main.

## Tests

El [fixture de perimetro](perimeter-fixture-snapshot.md) usa una base
Git inmutable por proceso y clones independientes sin reutilizar resultados.

Oraculo nuevo en tests/test_task_finish_perimeter.py. Reutiliza sin editar el
fixture real congelado de tests/test_generated_task_evidence.py y su preparacion
Git. Todas sus aprobaciones son sinteticas dentro de repos temporales.
Conservar los metodos y aserciones anteriores; la fase roja no es un cierre verde.

## Constraints

PARAR y reportar si se necesita otro modulo de produccion, modificar un oraculo
anterior, elevar budgets, ampliar el bundle confiable o alterar workflows.
Git local y oraculos del producto son los subprocess autorizados; no es un sandbox.
