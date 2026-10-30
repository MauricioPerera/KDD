---
type: 'Task Contract'
title: 'Diario Git de tareas'
description: 'Persistir operaciones de tarea mediante commits acotados en main y ramas de implementacion.'
tags: ['ccdd', 'git', 'tasks']
task: task-journal
intent: 'Persistir operaciones de tarea mediante commits acotados en main y ramas de implementacion.'
target: scripts/task_git.py
signature: 'def mutate(repo_root, operation, task_id, options) -> dict:'
test_command: 'python -m unittest tests/test_task_git.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tests/test_task_git.py'
tests_sha256: 'c8ffa61c37720ed5e6e1f6a2f29af01dccfb995c7d5bf6032f0cf92098d4c00a'
touch_only: ['scripts/task_git.py', 'scripts/task_evidence.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Persistir operaciones de tarea mediante commits acotados en main y ramas de implementacion. Ver [tareas Git](../git-tasks.md) y [modelo Task](../data_models/git-task.md).

## Interface
`def mutate(repo_root, operation, task_id, options) -> dict:` es la entrada testeada; la interfaz operativa se define en el nodo canonico.

## Invariants
- Solo muta sobre main con indice y arbol limpios, bajo lock exclusivo del coordinador.
- Crea como maximo una rama task/ID y no cambia de checkout ni publica al remoto.
- Cada operacion registra un commit del nodo; errores previos al commit restauran solo sus propios archivos y rama.
- ready compara contrato y oraculo con un SHA aprobado explicito y ancestro.
- finish exige rama integrada, ejecuta el oraculo reconocido y guarda evidencia durable del HEAD anterior.
- Un fallo, cero tests, timeout o cambios durante pruebas impiden done.

## Examples
- Crear TASK-001 y avanzar por estados permitidos produce nodos validos y commits acotados.
- Un salto backlog -> done, contrato re-sellado o indice ajeno modificado se rechaza.

## Do / Don't
- DO: usar la semantica y fronteras de confianza del modelo enlazado.
- DON'T: editar oraculos aprobados ni tratar un commit o un exit 0 vacio como aprobacion.

## Tests
La [preparacion local de Git](fixture-preparation-cost.md) conserva los commits,
la identidad y el mantenimiento de los repos reales del oraculo.
Oraculo independiente en `tests/test_task_git.py`, sellado antes de implementar.

## Constraints
- PARAR y reportar si cumplir exige modificar oraculos existentes o publicar cambios remotos.
- El uso de subprocess en diario/CLI/validador se limita a Git local y al runner documentado; el modelo puro no lo usa.
