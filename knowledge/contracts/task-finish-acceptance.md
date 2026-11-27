---
type: 'Task Contract'
title: 'Aceptación obligatoria para el cierre de tareas Git'
description: 'Ligar el estado done a dos pasadas de la matriz cuando el contrato aprobado declara una política de aceptación.'
tags: ['tasks', 'acceptance', 'board', 'evidence']
task: task-finish-acceptance
intent: 'Hacer que el cierre acredite la aceptación requerida sobre el mismo commit probado.'
target: scripts/task_git.py
signature: 'def _finish(root, task, options, head):'
test_command: 'python -m unittest tests.test_task_finish_acceptance'
test_runner: python-unittest
test_timeout: 240
tests: tests/test_task_finish_acceptance.py
tests_sha256: 'd1416a918fbea2e474bc62e5b5915265f141fda07412c8feb01089a8318e62ce'
oracle_files: ['tests/test_task_finish_acceptance.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py', 'scripts/task_evidence.py', 'scripts/validate_tasks.py', 'scripts/board_test_evidence.py', 'knowledge/git-tasks.md']
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 65
  params_max: 6
deps_allowed: ['stdlib', 'task_git', 'task_evidence', 'verify_acceptance', 'validate_tasks', 'board_test_evidence']
forbids: ['network', 'llm']
---

## Intent

Unir el [cierre de una tarea Git](../git-tasks.md) y la [aceptación por obligación](../acceptance.md). El piloto del banco de regresiones mostró un cierre válido para el oráculo de la tarea mientras la aceptación del producto se comprobaba en una ejecución aparte.

## Interface

El frontmatter del contrato aprobado puede declarar `acceptance_policy` con la ruta exacta de una política JSON v1 en el repositorio. `tasks.py finish` toma la declaración y la política del `approved_ref` de la tarea. La política incluye el propio contrato y puede incluir otros contratos del proyecto. Se conserva la entrada de cierre y la ruta canónica del recibo v2.

El recibo de un cierre con aceptación añade `acceptance` con los campos `policy`, `policy_sha256`, `approved_ref`, `tested_commit` y `checks`. Cada elemento de `checks` identifica `contract` y `obligation` y contiene `passes`. Cada pasada registra `iteration`, `executed`, `case_ids_sha256` y `output_sha256`. Las iteraciones se numeran 1 y 2. La huella de casos identifica el inventario de archivos e IDs de la pasada.

La proyección autenticada de Board para el recibo de una tarea ofrece el resumen `acceptance: {policy, policy_sha256, passes, checks}`. Los dos últimos campos son el número de pasadas y el número de filas de prueba acreditadas. La identidad de commits sigue en los campos de la respuesta del recibo.

## Invariants

- Resolver el requisito y la política por objetos originales de Git en el SHA aprobado. Exigir una ruta regular y el contrato de la tarea incluido en la política. El candidato y los argumentos de cierre carecen de autoridad para cambiar la selección aprobada.
- Conservar linaje, perímetro y comprobación de `main` limpio antes de iniciar la aceptación. Ejecutar el verificador existente sobre ese checkout y esa política. Toda obligación debe aprobar. Cada comando de prueba acredita dos pasadas completas con los mismos IDs, cero omisiones y sus límites declarados. Comprobar otra vez la identidad del checkout, del tip y de los archivos antes de publicar.
- Error, timeout, omisión, deriva de inventario, contrato ausente o política distinta bloquean el cierre. La tarea sigue en `in_progress` y conserva sus refs y su índice, con la causa en el diagnóstico.
- Registrar todas las filas ejecutables de la matriz, incluido el oráculo principal y los controles declarados de otros contratos. Reutilizar para los conteos v2 del oráculo de cierre una de las dos pasadas aceptadas del comando principal de la tarea. El cierre evita una tercera ejecución de ese comando.
- El diario comprueba offline las identidades, la huella de la política aprobada, la cobertura de filas y la pareja de pasadas por fila. Board muestra el resumen solo después de esa comprobación. La lectura histórica v1 y v2 conserva el significado del recibo de oráculo para contratos que carecen de la declaración.

## Examples

- Una tarea Python declara una política con su contrato y un contrato TypeScript. Se comprueban ambos runners dos veces y el recibo conserva el `approved_ref` y el `tested_commit` de la tarea.
- El oráculo de la tarea pasa y un control de otro contrato falla. `finish` deja la tarea en curso y muestra el fallo de aceptación.
- Una tarea histórica cierra con el oráculo gestionado que declaró su revisor. Su recibo v2 conserva el conteo por archivo.

## Do / Don't

- DO reutilizar `verify_acceptance` y el instrumento de ejecución existente. Guardar las huellas y el conteo en el recibo, con el mismo perímetro que verificó el diario.
- DO mantener la aprobación humana del baseline y la lectura de evidencia en Board.

## Tests

Las integraciones usan Git, el CLI de tareas y los runners reales de Python y Node sobre un proyecto temporal con Python y TypeScript. Comprueban éxito ligado al SHA, dos ejecuciones del oráculo principal, fallo en otra obligación, integridad de la política y cierre histórico. El oráculo también consulta el proyector real de Board y el validador del diario.

## Constraints

El alcance es la condición de cierre y su recibo. El detalle por caso y adjuntos pertenecen al visor. Se conservan los oráculos, Ubuntu, Windows y ambas pasadas de la suite. Cada comprobación mantiene su timeout aprobado. El cierre de aceptación de larga duración se ejecuta desde el CLI y Board lee el recibo resultante mediante su interfaz existente. El auditor offline conserva su bundle de cinco módulos y el cierre histórico mantiene su plazo.

PARAR y reportar si resulta necesario ampliar el perímetro aprobado o cambiar los límites de ejecución.
