---
type: 'Task Contract'
title: 'Modelo OKF de tareas Git'
description: 'Validar nodos Task y transiciones puras segun el modelo de tareas Git.'
tags: ['ccdd', 'git', 'tasks']
task: task-model
intent: 'Validar nodos Task y transiciones puras segun el modelo de tareas Git.'
target: scripts/task_model.py
signature: 'def validate_transition(before, after, completed=()) -> list:'
test_command: 'python -m unittest tests/test_task_model.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tests/test_task_model.py'
tests_sha256: '2b6e205611d902d45f3f1cc1337f4c5bde4311b385840d539415249bd2dd9dbc'
touch_only: ['scripts/task_model.py', 'scripts/validate_okf.py', 'knowledge/OKF-SPEC.md']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent
Validar nodos Task y transiciones puras segun el modelo de tareas Git. Ver [tareas Git](../git-tasks.md) y [modelo Task](../data_models/git-task.md).

## Interface
`def validate_transition(before, after, completed=()) -> list:` es la entrada testeada; la interfaz operativa se define en el nodo canonico.

## Invariants
- Nodos Task separados del contrato aprobado; IDs TASK-NNN, rama task/ID y cinco estados.
- Creacion solo en backlog; transiciones cerradas, identidad y aprobacion estables.
- ready exige referencia aprobada; in_progress exige responsable y base de rama.
- done exige referencia de pruebas y evidencia; dependencias deben estar done antes de iniciar.
- El parser rechaza claves duplicadas y el renderer conserva el cuerpo Markdown.

## Examples
- Crear TASK-001 y avanzar por estados permitidos produce nodos validos y commits acotados.
- Un salto backlog -> done, contrato re-sellado o indice ajeno modificado se rechaza.

## Do / Don't
- DO: usar la semantica y fronteras de confianza del modelo enlazado.
- DON'T: editar oraculos aprobados ni tratar un commit o un exit 0 vacio como aprobacion.

## Tests
Oraculo independiente en `tests/test_task_model.py`, sellado antes de implementar.

## Constraints
- PARAR y reportar si cumplir exige modificar oraculos existentes o publicar cambios remotos.
- El uso de subprocess en diario/CLI/validador se limita a Git local y al runner documentado; el modelo puro no lo usa.
