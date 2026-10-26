---
type: 'Task Contract'
title: 'Timeout real y diagnostico del fixture de tareas'
description: 'Fortalecer y estabilizar la prueba de cancelacion de tareas conservando la contencion y los nueve casos previos.'
tags: ['testing', 'processes', 'integration']
task: process-task-fixture
intent: 'Exigir un timeout real del oraculo y separar la falta de arranque de la supervivencia de descendientes.'
target: tests/test_process_tree_timeout.py
language: python
signature: 'def assert_cancelled(self, operation, delay=None, timeout=None):'
test_command: 'python -m unittest tests/test_process_task_fixture.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_process_task_fixture.py
tests_sha256: 'b0a983b675240c799ee878d34a65d63e512ce63e28b1fcd9c51a0b4b46245f62'
touch_only: ['tests/test_process_tree_timeout.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [reserva y clasificacion de tareas](../process-task-fixture.md), sin
cambiar el [runtime](process-tree-timeout.md) ni el resto del
[handshake](process-fixture-readiness.md). Revisar segun
[calidad](../quality-approval.md).

## Interface
assert_cancelled admite timeout opcional, predeterminado a FIXTURE_TIMEOUT=5.0.
Solo test_task_oracle_timeout_cleans_descendants usa TASK_ORACLE_TIMEOUT=15.0,
pasado al ejecutor y al helper. Devuelve el resultado de operation y conserva
el calendario absoluto desde antes del lanzamiento. El caso de tareas devuelve
la excepcion TASK_TESTS y exige causa subprocess.TimeoutExpired.

## Invariants
Conservar nueve metodos, todas las aserciones anteriores y los tres controles
de readiness existentes. Mantener no escrituras tardias y retorno menor que
timeout+6 s; la gracia maxima del producto sigue en 5 s. El fallo de readiness
nombra presentes/ausentes, elapsed, timeout y resultado. No aceptar otro error,
salida no cero ni ausencia del arbol como cancelacion correcta.

## Examples
- Arranque real retrasado 6 s: el caso de tareas llega al handshake y prueba
  cancelacion; el fixture de 5 s falla antes de observarlo.
- Salida no cero despues del handshake: rechazar aunque el runtime limpie hijos.
- Ejecutor sin contencion: rechazar por escritura tardia con readiness real.

## Do / Don't
- DO: conservar los intentos fallidos y medir el coste adicional de la reserva.
- DON'T: cambiar runtime, timeout por defecto de produccion, workers o workflows.

## Tests
tests/test_process_task_fixture.py ejecuta cinco controles de procesos reales:
arranque retrasado, salida no cero, fallo de carga, ausencia de descendientes y
supervivencia sin contencion. No simula PIDs, resultados ni el ciclo de vida.
No agrega SKIP ni reintento automatico y corre en Windows y Ubuntu.

## Constraints
PARAR y reportar si falta baseline humano explicito antes de adoptar/publicar
cambios del fixture. No quitar aserciones ni alterar otro oraculo congelado.
No prometer arranque bajo carga ilimitada. Nivel 2 no se afirma; budget declarativo.
