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
tests_sha256: 'e361f8b3f0047bb39cf13ba369eb5f4983cd3270100627f200463ae9cc6916a5'
oracle_files: ['tests/test_task_oracle_execution_proof.py', 'tests/test_task_git.py', 'tests/test_fixture_preparation.py', 'tests/test_generated_task_evidence.py', 'tests/__init__.py', 'tools/kdd-board/tests/task-oracle-execution-proof.test.ts', 'tools/kdd-board/tests/node-legacy-proof.test.ts']
touch_only: ['scripts/task_evidence.py', 'scripts/task_git.py', 'scripts/validate_tasks.py', 'scripts/oracle_execution.py', 'scripts/unittest_oracle_runner.py', 'scripts/node_oracle_reporter.mjs', 'tools/kdd-board/src/test-runner.ts', 'tools/kdd-board/src/task-execution.ts', 'tools/kdd-board/src/types.ts', 'tools/kdd-board/src/input-validation.ts', 'knowledge/git-tasks.md', 'knowledge/board-git.md', 'knowledge/data_models/git-task.md']
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
- Conservar la sintaxis historica de un solo archivo Python o Node, incluida
  la opcion TAP reconocida y el interprete Python declarado cuando este
  disponible. Aplicar el instrumento existente a esa seleccion.
  El modo UTF-8 explicito del interprete Python de tareas se conserva en el
  proceso aislado, incluida la lectura de archivos sin encoding declarado.
  El soporte de inventarios con varios modulos conserva su alcance actual.
- La lectura historica comprueba el recibo v1 con su semantica anterior.
  La auditoria v2 comprueba la identidad, la ruta seleccionada y el conteo
  sin ejecutar codigo ni importar el instrumento de ejecucion. El bundle
  congelado de cinco modulos de calidad sigue siendo suficiente para auditar.
  Una politica anterior con esos modulos protegidos requiere la revision
  ordinaria de sus nuevos bytes antes de aprobar cierres v2.
- Un skip de clase o modulo se trata como omision aunque unittest atribuya
  el callback al framework. El resultado no acredita un archivo parcialmente
  ejecutado. Conservar el timeout contenido y su diagnostico.
- Board legacy aplica el instrumento a Node con oraculo, conserva la
  verificacion Python, la salida diagnostica con redaccion de secretos y el
  alcance de los comandos libres sin oraculo. Un reporte Node previo sin
  identidad del nuevo instrumento no acredita la finalizacion al cargarlo.
  Si el reporter de Node registra casos aprobados y fallidos, el reporte de
  Board conserva esos conteos diagnosticos sin acreditar el cierre.
  El Board Git comparte el coordinador de tareas.
- Conservar los dos sistemas operativos, las dos pasadas de CI y los oraculos
  existentes. Los limites actuales de tiempo y el aislamiento de procesos del
  cierre siguen vigentes.

## Examples

- Un `node --test` con un archivo sin casos no acredita ningun caso.
- Un caso Python que pasa junto a una clase omitida impide el cierre.
- Un caso real produce evidencia v2 y pasa el auditor aislado de calidad.
- Un recibo v1 previo sigue siendo legible. Un v2 con resultado por archivo
  ausente es invalido aunque el JSON tenga un hash coherente.

## Do / Don't

- DO reutilizar el instrumento y conservar los diagnosticos de stdout y stderr.
- DON'T usar texto del candidato como prueba de que se ejecutaron casos.

## Tests

El oraculo crea tareas y merges con Git real, ejecuta Python y Node, audita el
recibo historico y comprueba el runner de Board con rutas anidadas.
Un cierre Python aislado lee UTF-8 de forma implicita. La suite Node
verifica la recarga de reportes y los conteos de un oraculo con un caso
aprobado y uno fallido usando el runner real de Board.
Los fixtures acotados copian los cuatro archivos existentes del instrumento
solo para la ejecucion viva, sin ampliar el bundle historico de auditoria.

## Constraints

La ejecucion de oraculos aprobados no es un sandbox. El contrato cubre el
resultado de los instrumentos confiables, no un actor con control del runner.

PARAR y reportar si el cambio requiere alterar un recibo historico o un oraculo congelado adicional.
