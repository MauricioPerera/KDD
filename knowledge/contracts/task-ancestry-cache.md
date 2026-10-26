---
type: 'Task Contract'
title: 'Pruebas positivas de ancestros limitadas a una operacion'
description: 'Reducir procesos Git para SHA inmutables sin reutilizar fallos ni refs mutables.'
tags: ['git', 'performance', 'integration']
task: task-ancestry-cache
intent: 'Conservar resultados de Git y evitar probar otra vez la misma relacion positiva de SHA durante una lectura.'
target: scripts/task_git.py
language: python
signature: 'def ancestor(root, before, after):'
test_command: 'python -m unittest tests/test_task_history_read_cost.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_task_history_read_cost.py
tests_sha256: '568010bf35df33140c91b159a9bc33e9a18254bccfde1845024c114729382f7a'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [politica de lectura y medicion](../task-history-read-cost.md)
sin alterar la [aprobacion de calidad](../quality-approval.md).

## Interface
Conservar ancestor(root, before, after) -> bool y object_cache(). Sin nuevas
opciones de CLI, dependencias ni cache persistente.

## Invariants
Cumplir el nodo enlazado: solo pruebas positivas de Git para SHA completos,
clave por repositorio, descarte al terminar, consultas frescas para refs,
negativos y errores. Conservar los controles de integracion y evidencia.

## Examples
- Repetir veinte veces el mismo par positivo dentro de una operacion usa una prueba Git.
- Mover main, terminar la operacion o cambiar de repositorio exige otra consulta.

## Do / Don't
- DO: medir procesos reales y conservar las salidas y el inventario anterior.
- DON'T: cachear True inventados, errores, False o nombres simbolicos.

## Tests
Oraculo compartido con task-history-parent-batch: Git real, Trace2,
objetos nuevos, merges, SHA256, refs moviles, excepciones y operaciones
independientes. Sin mocks de respuestas de Git ni SKIP.

## Constraints
PARAR y reportar si se necesita cambiar un oraculo previo, aprobar un
runtime, editar workflows o modificar protecciones. El baseline nuevo
requiere revision humana antes de implementar.
