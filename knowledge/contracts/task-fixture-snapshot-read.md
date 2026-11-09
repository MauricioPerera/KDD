---
type: 'Task Contract'
title: 'Capturar HEAD y estado del fixture en una lectura Git'
description: 'Obtener el commit y el estado de trabajo en la misma consulta de Git para las pruebas de tareas.'
tags: ['ci', 'fixtures', 'git', 'performance']
task: task-fixture-snapshot-read
intent: 'Reducir los procesos Git de las capturas de control sin debilitar las comparaciones.'
target: tests/test_generated_task_evidence.py
signature: 'def snapshot(self):'
test_command: 'python -m unittest tests.test_postinit_repeated_git.FixtureSnapshotRead'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_postinit_repeated_git.py
tests_sha256: 'b6fab2d5d91bdc52f513a2f76c73e568739db82dd1a282f19fbf148cbfe05f81'
oracle_files: ['tests/test_postinit_repeated_git.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['tests/test_generated_task_evidence.py']
deps_allowed: ['stdlib', 'git']
forbids: ['network', 'llm']
---

## Intent
Reducir el coste de las capturas que ejercitan los controles de
[operaciones de tarea](task-operation-controls.md) y de
[evidencia generada](quality-task-evidence.md).

## Interface
Mantener las cuatro claves head, branches, status y tree de TaskProject.snapshot.
En repositorios con HEAD canonico, obtener HEAD y el estado del checkout
mediante la misma consulta porcelain v2, con un total de tres procesos Git.
Cada llamada vuelve a observar HEAD, todas las ramas locales, el estado del
checkout y el arbol del indice. Para HEAD ausente o una cabecera no utilizable,
conservar la consulta y los fallos anteriores.

## Invariants
- Conservar las comparaciones del fixture antes y despues de operaciones reales.
  Cambios de HEAD con el mismo arbol, ramas, indice y archivos sin seguimiento
  deben producir diferencias. Ningun dato se recupera de una captura anterior.
- Preservar la informacion de los registros porcelain, incluidas las rutas
  con espacios o Unicode y el origen de renombres con prefijo de cabecera.
  Separar los metadatos de rama al comienzo de la salida y conservar
  el escapado de rutas aplicado por Git.
- Mantener los metodos y asserts congelados, los repositorios por caso,
  el oraculo real de cada operacion y las dos suites en ambos sistemas.
  El cambio propuesto del fixture se revisa con su sello actualizado.

## Examples
- Un commit vacio cambia head aunque tree y status coincidan.
- Staged revertido en el checkout cambia tree y status.

## Do / Don't
- DO medir el proceso real de Git y contrastar el indice y las refs.
- DON'T cachear el estado ni reemplazar las operaciones reales del oraculo.

## Tests
Cuatro casos con Git real para presupuesto en los dos formatos, cambio de
HEAD, indice, ramas, renombre, archivos nuevos y HEAD sin commit.

## Constraints
PARAR y reportar si se requiere modificar otro fixture congelado. La mejora
local no acredita el umbral de 480 s para tres CI consecutivos de main.
