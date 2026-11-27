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
tests_sha256: '8e3269fc2d11bdf3013014414c2f84d3cee03615605697bb0dcccaeb317c9b3a'
oracle_files: ['tests/test_task_finish_acceptance.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py']
touch_only: ['scripts/tasks.py', 'scripts/task_git.py', 'scripts/task_evidence.py', 'scripts/verify_acceptance.py', 'scripts/oracle_execution.py', 'scripts/validate_tasks.py', 'scripts/board_test_evidence.py', 'knowledge/git-tasks.md']
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 65
  params_max: 6
deps_allowed: ['stdlib', 'task_git', 'task_evidence', 'verify_acceptance', 'oracle_execution', 'process_tree', 'validate_tasks', 'board_test_evidence']
forbids: ['network', 'llm']
---

## Intent

Unir el [cierre de una tarea Git](../git-tasks.md) y la [aceptación por obligación](../acceptance.md). El piloto del banco de regresiones mostró un cierre válido para el oráculo de la tarea mientras la aceptación del producto se comprobaba en una ejecución aparte.

## Interface

El frontmatter del contrato aprobado puede declarar `acceptance_policy` con la ruta exacta de una política JSON v1 en el repositorio. `tasks.py finish TASK-ID --verify-acceptance` toma la declaración y la política del `approved_ref` de la tarea. La política incluye el propio contrato y puede incluir otros contratos del proyecto. La opción confirma la ejecución local de la matriz. Para una tarea con esa declaración, el CLI ordinario devuelve `TASK_ACCEPTANCE` y muestra la opción antes de iniciar pruebas. Board conserva el error genérico de su coordinador `TASK_UNAVAILABLE` en esa operación y permite consultar el recibo después del cierre por CLI. Se conserva la ruta canónica del recibo v2.

El recibo de un cierre con aceptación añade `acceptance` con los campos `policy`, `policy_sha256`, `approved_ref`, `tested_commit` y `checks`. Cada elemento de `checks` identifica `contract` y `obligation` y contiene `passes`. Cada pasada registra `iteration`, `executed`, `case_ids_sha256` y `output_sha256`. Las iteraciones se numeran 1 y 2. La huella de casos usa el JSON UTF-8 compacto con claves ordenadas del inventario de rutas relativas y sus listas de IDs ordenados.

La proyección autenticada de Board para el recibo de una tarea ofrece el resumen `acceptance: {policy, policy_sha256, passes, checks}`. Los dos últimos campos son el número de pasadas y el número de filas de prueba acreditadas. La identidad de commits sigue en los campos de la respuesta del recibo.

## Invariants

- Resolver el requisito y la política por objetos originales de Git en el SHA aprobado. Exigir una ruta regular y el contrato de la tarea incluido en la política. El candidato y los argumentos de cierre carecen de autoridad para cambiar la selección aprobada.
- Conservar linaje, perímetro y comprobación de `main` limpio antes de iniciar la aceptación. Cotejar con el commit probado las rutas de implementación de la política y los targets de todos sus contratos, con las reglas vigentes para texto y binarios. Repetir las comprobaciones del checkout, del tip y de los archivos antes de publicar.
- Ejecutar el verificador existente sobre ese checkout y esa política. El cierre conecta cada comando de la matriz a la [contención de árbol de procesos](process-tree-timeout.md), con su propio timeout y limpieza acotada de descendientes. Dos ejecuciones reales por fila acreditan la misma identidad de casos, cero omisiones y aprobación. El verificador independiente conserva su interfaz y modo de ejecución por defecto.
- Error, timeout, omisión, deriva de inventario, contrato ausente o política distinta bloquean el cierre. La tarea sigue en `in_progress` y conserva sus refs y su índice, con la causa en el diagnóstico.
- Registrar todas las filas ejecutables de la matriz, incluido el oráculo principal y los controles declarados de otros contratos. Reutilizar para el resto del recibo v2 la segunda pasada aceptada del comando principal de la tarea. Su conteo y `output_sha256` coinciden en ambos registros. El cierre evita una tercera ejecución de ese comando.
- El diario exige el bloque `acceptance` cuando el contrato aprobado lo declara. Comprueba offline las identidades, la huella de la política aprobada, sus filas esperadas, las pasadas de cada fila y la relación con el recibo del oráculo principal. Board devuelve el resumen después de esa comprobación. La lectura histórica v1 y v2 conserva el significado del recibo de oráculo para contratos que carecen de la declaración.

## Examples

- Una tarea Python declara una política con su contrato y un contrato TypeScript. Se comprueban ambos runners dos veces y el recibo conserva el `approved_ref` y el `tested_commit` de la tarea.
- El oráculo de la tarea pasa y un control de otro contrato falla. `finish` deja la tarea en curso y muestra el fallo de aceptación.
- Una tarea histórica cierra con el oráculo gestionado que declaró su revisor. Su recibo v2 conserva el conteo por archivo.

## Do / Don't

- DO reutilizar `verify_acceptance` y el instrumento de ejecución existente. Guardar las huellas y el conteo en el recibo, con el mismo perímetro que verificó el diario.
- DO mantener la aprobación humana del baseline y la lectura de evidencia en Board.

## Tests

Las integraciones usan Git, el CLI de tareas y los runners reales de Python y Node sobre un proyecto temporal con Python y TypeScript. Comprueban cuántas veces se ejecuta cada fila sobre el SHA probado, el enlace entre la segunda pasada y el recibo, el rechazo del cierre ordinario y el fallo de una obligación después de pasar ambos oráculos principales. Detectan también un archivo de implementación con bytes distintos de ese SHA y una obligación cuyo proceso hijo mantiene abierto un pipe al vencer su timeout. El proyector real de Board y el validador del diario comprueban además un recibo con identidad de aceptación inconsistente.

## Constraints

El alcance es la condición de cierre y su recibo. El detalle por caso y adjuntos pertenecen al visor. Se conservan los oráculos, Ubuntu, Windows y ambas pasadas de la suite. Cada comprobación mantiene su timeout aprobado. El cierre con aceptación se ejecuta desde el CLI y Board lee el recibo resultante por su interfaz existente. El auditor offline usa sus cinco módulos base y la extensión aprobada de inventario que ya admite. La aceptación independiente y el cierre histórico conservan su comportamiento.

PARAR y reportar si resulta necesario ampliar el perímetro aprobado o cambiar los límites de ejecución.
