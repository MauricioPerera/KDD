---
type: 'Task Contract'
title: 'Evidencia instrumentada para el cierre de tareas'
description: 'Acreditar casos reales por archivo al cerrar tareas Git y verificar oraculos desde Board.'
tags: ['tasks', 'board', 'evidence', 'security']
task: task-oracle-execution-proof
intent: 'Exigir evidencia instrumentada de los casos que ejecuta un oraculo de tarea.'
target: scripts/task_evidence.py
signature: 'def execute(metadata, root, timeout=120):'
test_command: 'python -m unittest tests.test_task_oracle_execution_proof'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 6
tests: tests/test_task_oracle_execution_proof.py
tests_sha256: '876dfaaaf4535bacae6b782ab5597a4f26a132f02fd761bd8e8ac03cc51a5354'
oracle_files: ['tests/test_task_oracle_execution_proof.py', 'tests/test_task_git.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'tools/kdd-board/tests/task-oracle-execution-proof.test.ts']
touch_only: ['scripts/task_evidence.py', 'scripts/task_git.py', 'scripts/validate_tasks.py', 'scripts/oracle_execution.py', 'tools/kdd-board/src/test-runner.ts', 'knowledge/git-tasks.md', 'knowledge/board-git.md', 'knowledge/data_models/git-task.md']
deps_allowed: ['stdlib', 'oracle_inventory', 'oracle_execution', 'process_tree']
forbids: ['network', 'llm']
---

## Intent

Reparar la garantia de casos reales del [diario Git](task-journal.md) y de
[Board](board-oracle-execution.md) mediante el [runner gestionado](oracle-execution.md).

## Interface

Conservar las entradas `tasks.py ready`, `tasks.py finish`,
`validate_tasks.py` y la API publica de Board. Los cierres nuevos producen
un recibo `schema_version: 2` en la misma ruta canonica. Conserva los campos
de identidad, resultado, salida y perimetro anteriores. `oracle_results` mapea
cada archivo seleccionado, por ruta exacta relativa al repo, a
`{"executed": N, "skipped": 0, "ok": true}`. `passed_tests` suma esos casos.

## Invariants

- Un archivo contenedor Node, un resumen unittest impreso, cero casos, un
  archivo seleccionado sin resultado, un caso omitido, un timeout o una salida
  temprana impiden publicar un cierre. El nodo queda `in_progress` y el
  coordinador no escribe evidencia ni commit.
- Los contratos de un solo archivo sin runner explicito conservan su sintaxis
  historica Python/Node y obtienen evidencia instrumentada. Los contratos con
  runner e inventario explicitos admiten los archivos seleccionados por la
  gramática gestionada. Se requiere incluir el oraculo principal.
- Para un contrato gestionado, el inventario revisado, incluidos los helpers,
  se conserva en el arbol aprobado, el commit probado y el checkout. Un cambio
  de archivo inventariado bloquea antes de ejecutar el oraculo. Se mantienen
  los controles de estado y bytes posteriores a la ejecucion.
- La lectura historica comprueba el recibo v1 con su semantica anterior.
  La auditoria de un recibo v2 comprueba la identidad, las rutas seleccionadas
  y los conteos sin ejecutar codigo ni requerir un checkout del commit probado.
  Los consumidores historicos de evidencia v1 deben poder seguir leyendola.
- Board legacy aplica el instrumento a Node con oraculo, conserva la
  verificacion Python, la redaccion de secretos y el alcance de los comandos
  libres sin oraculo. El Board Git comparte el coordinador de tareas.
- Conservar los dos sistemas operativos, las dos pasadas de CI y los oraculos
  existentes. Los limites actuales de tiempo y el aislamiento de procesos del
  cierre siguen vigentes.

## Examples

- Un `node --test` con un archivo sin casos no acredita ningun caso.
- Dos modulos Python inventariados con un caso cada uno producen un recibo v2
  con dos rutas y dos casos. Cambiar un helper inventariado impide el cierre.
- Un recibo v1 previo sigue siendo legible. Un v2 con resultado por archivo
  ausente es invalido aunque el JSON tenga un hash coherente.

## Do / Don't

- DO reutilizar el instrumento y conservar los diagnosticos de stdout y stderr.
- DON'T usar texto del candidato como prueba de que se ejecutaron casos.

## Tests

El oraculo crea tareas y merges con Git real, ejecuta Python y Node, audita el
recibo historico y comprueba el runner de Board con rutas anidadas.

## Constraints

La ejecucion de oraculos aprobados no es un sandbox. El contrato cubre el
resultado de los instrumentos confiables, no un actor con control del runner.

PARAR y reportar si el cambio requiere alterar un recibo historico o un oraculo congelado adicional.
