---
type: 'Task Contract'
title: 'Lecturas Git agrupadas en ready y finish'
description: 'Agrupar identidad y artefactos con lecturas frescas.'
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
tests_sha256: 'ae7ec2a0b9086cc12c947420c46d87022335cacbbacf04236a120a59ca71d6d0'
oracle_files: ['tests/test_task_transition_read_cost.py', 'tests/test_git_task_multi_oracle.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'scripts/trusted_ci.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'git', 'task_model', 'task_evidence', 'validate_tasks']
forbids: ['network', 'llm']
---

## Intent

Reducir trabajo repetido observado en [oraculos multiarchivo](git-task-multi-oracle.md).
Conservar la [lectura de inventario por etapa](task-oracle-snapshot-batch.md).

## Interface

Conservar CLI y recibos. Antes del listado de tareas se permiten tres
arranques: lock, lote de raiz/formato/HEAD^{commit} y status. Reusar la prueba
solo cuando status confirme el mismo SHA en main limpio. Con formato
conocido, la comparacion fria de cuatro artefactos usa un lote Git.

## Invariants

- Acotar la prueba al lock y la operacion. Ante Git antiguo, salida ambigua o
  SHA distinto, volver a las lecturas independientes o rechazar. SHA-1 y SHA-256.
- Conservar ascendencia, perimetro, modos, sello e inventario sin reemplazos.
  Releer inventario, artefactos, main, punta y limpieza despues del oraculo.
- Conservar el primer error por ruta y rechazar objetos faltantes. Un cierre
  rechazado no crea commit ni recibo.
- Conservar los 2563 IDs, Ubuntu/Windows, dos pasadas y cobertura inicial.
  Post-init Windows sigue bajo el plazo comun de 600 s.

## Examples

- Ready SHA-256 reutiliza el HEAD comprobado.
- El oraculo que mueve la punta o altera el target impide cerrar.

## Do / Don't

Usar Trace2 y Git real. Separar las lecturas previas y posteriores al runner.

## Tests

Prever presupuesto por etapa, checkout anidado, avance de main, movimiento
de punta, deriva oculta por status y cuatro artefactos frios.

## Constraints

PARAR y reportar si falta la aprobacion del baseline o se requieren cambios de
workflow, runtime o protecciones. Medir tres ejecuciones
del mismo SHA y publicar los tiempos de pared, etapas e inventarios.
