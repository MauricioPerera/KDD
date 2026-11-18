---
type: 'Task Contract'
title: 'Lecturas Git agrupadas en ready y finish'
description: 'Agrupar identidad inicial y artefactos de cierre con comprobaciones frescas por etapa.'
tags: ['tasks', 'git', 'performance', 'integration']
task: task-transition-read-cost
intent: 'Reducir los arranques Git durante las transiciones ready y finish.'
target: scripts/task_git.py
signature: 'def _prepare(root, operation, task_id, options):'
test_command: 'python -m unittest tests.test_task_transition_read_cost'
test_runner: python-unittest
test_scope: infrastructure
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_task_transition_read_cost.py
tests_sha256: 'de4d09f53c6cd8cf0afb0f5a59c59f1f6920ebe85ba18729e91d05b70e87dda0'
oracle_files: ['tests/test_task_transition_read_cost.py', 'tests/test_git_task_multi_oracle.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'scripts/trusted_ci.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'git', 'task_model', 'task_evidence', 'validate_tasks']
forbids: ['network', 'llm']
---

## Intent

Reducir trabajo repetido observado en [oraculos multiarchivo](git-task-multi-oracle.md).
Conservar la [lectura de inventario por etapa](task-oracle-snapshot-batch.md).

## Interface

Conservar las CLI de tareas y la evidencia de cierre. En el arranque valido de
ready y finish, una consulta Git acredita raiz, formato nativo y commit de HEAD.
El status posterior debe acreditar el mismo SHA, main y checkout limpio antes
de reutilizar la prueba en la auditoria inicial. En la comparacion fria de
artefactos de cierre con formato conocido, un lote Git basta para cuatro blobs.

## Invariants

- Mantener la identidad bajo el lock y limitarla a la operacion. Si Git devuelve
  formato antiguo, salida ambigua o HEAD distinto en status, hacer las lecturas
  independientes originales o rechazar. Soportar SHA-1 y SHA-256.
- Mantener verificacion de ascendencia, perimetro, modos, sello e inventario
  original sin reemplazos. Leer el inventario y el checkout de nuevo despues
  del oraculo. Revalidar main, punta de tarea y limpieza antes de publicar.
- Comparar cada artefacto y conservar su diagnostico. Rechazar deriva y
  objetos faltantes. Un cierre rechazado no crea recibo ni commit de tarea.
- Conservar los 2563 IDs de main, las dos pasadas en Ubuntu y Windows, cobertura
  inicial y la ventana comun de post-init Windows inferior a 600 segundos.

## Examples

- Ready con SHA-256 reutiliza el HEAD comprobado para la auditoria inicial.
- Un oraculo que mueve la punta de la tarea deja el cierre rechazado.
- Cuatro blobs frios del cierre se consultan en un solo lote de contenidos.

## Do / Don't

Usar Trace2 y Git real. Reutilizar el contexto de objetos vigente. Mantener
separadas las comprobaciones antes y despues del runner.

## Tests

Cubrir presupuesto por etapa, exito en los dos formatos, rechazo de checkout
anidado, cambio real de rama durante el oraculo y lectura fria de artefactos.

## Constraints

PARAR y reportar si falta la aprobacion del baseline o se requieren cambios de
workflow, runtime o protecciones. Medir tres ejecuciones
del mismo SHA y publicar los tiempos de pared, etapas e inventarios.
