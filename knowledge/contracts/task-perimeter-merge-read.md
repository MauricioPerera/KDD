---
type: 'Task Contract'
title: 'Leer el merge del perimetro en el recorrido Git'
description: 'Obtener el diff del primer padre en la misma lectura que las filas del recorrido de perimetro.'
tags: ['tasks', 'git', 'performance', 'integration']
task: task-perimeter-merge-read
intent: 'Eliminar el segundo proceso Git del perimetro lineal conservando todas sus pruebas.'
target: scripts/task_git.py
signature: 'def _perimeter_paths(root, context):'
test_command: 'python -m unittest tests.test_postinit_repeated_git.PerimeterMergeRead'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_postinit_repeated_git.py
tests_sha256: 'b6fab2d5d91bdc52f513a2f76c73e568739db82dd1a282f19fbf148cbfe05f81'
oracle_files: ['tests/test_postinit_repeated_git.py', 'tests/test_task_perimeter_stage_batch.py', 'tests/test_task_history_read_cost.py', 'tests/test_traceability_model.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_model', 'task_evidence', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Reducir el coste de la lectura descrita en [task-perimeter-stage-batch](task-perimeter-stage-batch.md).
Mantener el [protocolo de medicion](../postinit-proof-cost.md).

## Interface
El recorrido frio con tres OID canonicos, una historia de implementacion
lineal y un merge de dos padres reconocido usa como maximo un proceso Git.
La lista de cambios conserva los commits propios y el diff del merge contra
su primer padre. La lectura del DAG incluye las dos ramas.

## Invariants
- Preservar la union de cambios propios, incluidos los revertidos, y las
  resoluciones introducidas por el merge. Excluir cambios ajenos de main.
- Validar el framing y las identidades nativas SHA-1 y SHA-256 antes de
  interpretar filas y rutas. Preservar nombres con Unicode, tab y salto de linea.
- Con Git incompatible, salida ambigua, error o grafo no reconocido,
  conservar la comprobacion serial y sus rechazos. Revalidar en otra operacion
  cuando cambie un reemplazo. Conservar refs, indice, config y checkout.
- Agrupar solo lecturas de esta etapa. Mantener la auditoria de transiciones,
  comprobaciones de artefactos, oraculos, ambos sistemas y ambas pasadas.

## Examples
- Un merge que introduce una ruta fuera de alcance conserva esa ruta.
- Un merge sin cambios contra el primer padre conserva los cambios revertidos
  de la rama de implementacion.

## Do / Don't
- DO contar procesos Git reales con Trace2 y comparar la salida con Git.
- DON'T reemplazar la historia por el diff entre extremos.

## Tests
Git real con ambos formatos, resolucion de merge, ruta compleja, merge sin
diff y sustitucion temporal de un objeto Git seguida de recuperacion.

## Constraints
PARAR y reportar si falta el baseline aprobado o se necesita ampliar el
perimetro. El cierre exige tres CI consecutivos del SHA final en main y
post-init Windows inferior a 480 s en cada uno.
