---
type: 'Task Contract'
title: 'Publicar el diario de tareas mediante merge'
description: 'Auditar el historial original importado por un merge sin perder estados ni aceptar snapshots fabricados.'
tags: ['ccdd', 'git', 'tasks']
task: task-publication
intent: 'Permitir publicar un diario preservado mediante PR con las mismas garantias de transicion y evidencia.'
target: scripts/validate_tasks.py
signature: 'def validate_range(repo_root, base_ref, head_ref) -> list:'
test_command: 'python -m unittest tests/test_task_publication.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tests/test_task_publication.py'
tests_sha256: b85d174f28d29d0bb44d765ca158eb932aebb3ac107cc62a6f5a6d078cc04269
touch_only: ['scripts/validate_tasks.py', 'scripts/task_git.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Publicar el diario preservando commits conforme a [tareas Git](../git-tasks.md)
y las pruebas de cierre del [modelo Task](../data_models/git-task.md).

## Interface
`validate_range(repo_root, base_ref, head_ref)` devuelve errores sin modificar Git.
`task_git.history(repo_root, task_id)` conserva los commits originales importados.

## Invariants
- La referencia base publica sigue perteneciendo a la cadena de primeros padres.
- Un merge de dos padres puede importar nodos identicos al segundo padre si el
  primer padre no los cambio desde la bifurcacion; cuerpo y metadatos se comparan.
- Se audita cada transicion original desde la bifurcacion, incluidos estados
  intermedios y merges anidados; un snapshot final valido no basta.
- Las reglas originales de alcance, aprobacion y cierre siguen vigentes en los
  commits fuente. El merge de publicacion no es una nueva transicion de estado.
- Conflictos de tarea, cambios inventados en merge y snapshots squash se rechazan.
- El historial muestra los commits de estados originales sin duplicar merges.

## Examples
- Un PR con backlog, ready, in_progress y done conserva su evidencia y pasa.
- Un salto directo a done o sobrescribir otra decision de main falla.

## Do / Don't
- DO: preservar los SHA originales y comprobar toda la cadena importada.
- DON'T: reescribir evidencia, debilitar oraculos existentes ni aprobar baselines.

## Tests
Oraculo independiente `tests/test_task_publication.py`, sellado antes de implementar.
Incluye publicacion completa, parcial, conflictos, manipulación y squash.

## Constraints
- PARAR y reportar si cumplir exige modificar un oraculo existente.
- Solo Git local y stdlib; no ejecutar codigo del candidato durante la auditoria.
