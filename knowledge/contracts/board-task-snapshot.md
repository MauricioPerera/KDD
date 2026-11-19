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
tests_sha256: 'fb8235cef4c32ec9cad7f62754c1bbeb3d0c6558f15e6221b38c0903ce7999c0'
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
Board comprueba main antes y despues de leer. Un error del hijo se propaga.
Un detalle exitoso con main estable invoca un coordinador directo.
Una transicion exitosa con main estable invoca dos, sin contar sus oraculos.
Solo la consulta combinada permite hasta 16 MiB y 360 segundos. Son los
presupuestos acumulados de las dos consultas previas de 8 MiB y 180 segundos.
Los demas comandos conservan sus limites individuales.

## Invariants

- Resolver main una vez en el hijo. Leer nodo e historia desde ese SHA,
  sin usar checkout ni seguir main por separado para los dos resultados.
- Agrupar hasta 32 versiones de la tarea por lote. El detalle estable
  usa hasta ocho arranques Git con siete registros y nueve con 35.
- Validar el inventario y todo el diario en el SHA observado antes de
  mutar. Conservar rechazos y la verificacion independiente bajo el lock.
- Conservar CLI previa, permisos, lock, validacion del coordinador y recibos.
  Conservar 2563 IDs, Ubuntu/Windows, dos pasadas, cobertura inicial y 600 s.

## Examples

- El diario importado conserva los SHA originales al consultar desde otra rama.
- Si una lectura exitosa observa main cambiado, Board vuelve a leer.
- Un diario corrupto no permite publicar ready.
- Un resultado antes admitido por separado puede superar 8 MiB al combinarse.

## Do / Don't

Usar Git y procesos Node/Python reales. Evitar caches entre peticiones.

## Tests

Contar procesos reales y probar el pin, la carrera, la corrupcion intermedia
y la compatibilidad de resultados.

## Constraints

PARAR y reportar si faltan aprobacion de baseline o cambios por revisar en
workflows, runtime o protecciones. Separar medicion del piloto y del job.
