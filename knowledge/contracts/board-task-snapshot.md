---
type: 'Task Contract'
title: 'Una lectura del nodo y diario Git en Board'
description: 'Reducir arranques del coordinador y de Git en el piloto de dependencias.'
tags: ['tasks', 'git', 'kdd-board', 'performance']
task: board-task-snapshot
intent: 'Agrupar el detalle Git de una tarea en un solo coordinador.'
target: tools/kdd-board/src/git-task-store.ts
language: typescript
signature: 'GitTaskStore.get(id), GitTaskStore.transition(id, input)'
test_command: 'python -m unittest tests.test_board_task_snapshot'
test_runner: python-unittest
test_scope: infrastructure
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 5
tests: tests/test_board_task_snapshot.py
tests_sha256: '9ead9fcfc40d3a2facc047563ec1b72c584ff75f06a539bc0e71027d013bde09'
oracle_files: ['tests/test_board_task_snapshot.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'scripts/trusted_ci.py', 'tests/__init__.py']
touch_only: ['tools/kdd-board/src/git-task-store.ts', 'scripts/tasks.py', 'scripts/task_git.py']
deps_allowed: ['node', 'stdlib', 'git']
forbids: ['network', 'llm']
---

## Intent

Reducir lecturas duplicadas del [piloto real](dependency-workflow-e2e.md).
Conservar el [diario de Board](board-git-journal.md).

## Interface

`tasks.py snapshot ID --json` devuelve `task` y `journal` desde un SHA de main.
Board conserva sus respuestas y comprueba main antes y despues de cada intento.
Un detalle estable invoca Python una vez y una transicion exitosa dos veces.

## Invariants

- Resolver main una vez en el hijo. Leer nodo e historia desde ese SHA,
  sin usar checkout ni seguir main por separado para los dos resultados.
- Leer blobs de la tarea en lotes acotados. Con siete registros, un detalle
  estable usa como maximo ocho arranques Git, contando ambos de Board.
- Conservar diarios, errores y reintento de Board. Una entrada malformada
  intermedia impide una mutacion aunque el nodo actual sea valido.
- Conservar CLI previa, permisos, lock, validacion del coordinador y recibos.
  Conservar 2563 IDs, Ubuntu/Windows, dos pasadas, cobertura inicial y 600 s.

## Examples

- Consultar desde otra rama devuelve el diario de main.
- Si main cambia durante la lectura, Board repite la consulta.
- Un diario corrupto no permite publicar ready.

## Do / Don't

Usar Git y procesos Node/Python reales. Evitar caches entre peticiones.

## Tests

Contar procesos reales y probar el pin, la carrera, la corrupcion intermedia
y la compatibilidad de resultados.

## Constraints

PARAR y reportar si faltan aprobacion de baseline o cambios por revisar en
workflows, runtime o protecciones. Separar medicion del piloto y del job.
