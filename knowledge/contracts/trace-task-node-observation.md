---
type: 'Task Contract'
title: 'Interpretar nodos Task de la misma lectura regular de Git'
description: 'Eliminar una lectura duplicada al proyectar los nodos de tareas desde Git.'
tags: ['traceability', 'git', 'performance', 'integration']
task: trace-task-node-observation
intent: 'Reducir lecturas Git y preservar la identidad de los bytes interpretados en la proyeccion.'
target: scripts/traceability_git.py
signature: 'def tasks(self):'
test_command: 'python -m unittest tests.test_trace_task_node_observation'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_trace_task_node_observation.py
tests_sha256: 'b00afb426661b8993c668be04f73481495ba8bb29e0807d4795177e659d8739a'
oracle_files: ['tests/test_trace_task_node_observation.py', 'tests/test_traceability_contract_batch.py', 'tests/test_traceability_model.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/traceability_git.py', 'scripts/task_git.py', 'scripts/validate_tasks.py']
deps_allowed: ['stdlib', 'task_git', 'task_model', 'traceability_model', 'task_evidence', 'validate_tasks', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Reducir la lectura duplicada en la fase de nodos de
[trazabilidad Git](traceability-git.md), conservando la
[frescura de la proyeccion](trace-projection-fresh-read.md).

## Interface
Conservar `_Projection.tasks`, `read_nodes`, `read_tasks` y `build_trace`.
Enumerar los nodos, observar su modo regular y contenido y analizar esos
mismos bytes con las reglas del diario. Para un nodo frio, con formato ya
conocido y Git que soporta objectmode, usar una lectura de inventario y una
lectura fresca del contenido. Conservar el fallback de lectura regular.

## Invariants
- Mantener el orden de las verificaciones de modo y despues de interpretacion,
  los errores de ruta, el identificador canonico y la exclusion de index.md.
- Un cache previo de blobs del diario no puede sustituir el nodo que acaba
  de observar la proyeccion. Conservar la frescura ante reemplazos Git.
  Un blob regular observado con UTF-8 invalido se rechaza. Si se requiere
  la lectura alternativa, obtener el contenido fresco del OID regular que
  identifico ls-tree. No recuperar el contenido de la cache del diario.
- La auditoria de snapshots, historia, evidencia y producto sigue ejecutandose.
  La proyeccion no instala resultados ni bytes propios en el cache del diario.
  Antes de acreditar el diario, exigir que los nodos proyectados coincidan
  con los registros usados por la comprobacion canonica del snapshot de la
  revision observada. Capturar la comprobacion de esos registros durante
  el snapshot, con alcance de raiz y revision y sin cambiar las firmas
  publicas. No reconstruir los registros con una relectura posterior.
  Una divergencia o la ausencia de la comprobacion produce TRACE_JOURNAL
  y no publica un enlace verificado.
- Conservar los 2.220 IDs, ambos sistemas, las dos pasadas y el presupuesto
  de post-init. El objetivo se mide con el comando completo del mismo SHA.

## Examples
- Nodo regular: dos procesos en la etapa fria de un nodo y los mismos campos.
- Cache previo valido y reemplazo con nodo malformado: error de interpretacion.
- Nodo enlazado: mismo error de ruta que la lectura serial.

## Do / Don't
- DO comprobar las dos variantes de formato con Git real y Trace2.
- DON'T leer una etapa posterior, ejecutar el producto o reciclar un PASS.

## Tests
Repositorios reales para el presupuesto, un reemplazo con cache caliente,
error de modo y un nodo anidado. Se prueban bytes invalidos, la via
alternativa y la prioridad de modos en un inventario con dos nodos.
La regresion mantiene los oraculos de
reemplazo durante proyeccion, los alias y el historial.

## Constraints
PARAR y reportar si falta el baseline aprobado o se requiere cambiar
runtime, workflow o proteccion.
