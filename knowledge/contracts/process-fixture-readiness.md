---
type: 'Task Contract'
title: 'Fixture de procesos con arranque observable y control negativo real'
description: 'Estabilizar la precondicion del oraculo sin cambiar la cancelacion del runtime ni rebajar sus aserciones.'
tags: ['testing', 'processes', 'integration']
task: process-fixture-readiness
intent: 'Distinguir falta de arranque de descendientes supervivientes y conservar la prueba del deadline de lanzamiento.'
target: tests/test_process_tree_timeout.py
language: python
signature: 'def assert_cancelled(self, operation, delay=None):'
test_command: 'python -m unittest tests/test_process_fixture_startup.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_process_fixture_startup.py
tests_sha256: '0c01a1db44eea19ee502614e6309d6f626ccfc4aad9763d2f69f8ff0121d74f8'
touch_only: ['tests/test_process_tree_timeout.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [protocolo de readiness](../process-fixture-readiness.md), conservando
el [contrato de runtime](process-tree-timeout.md) y la [revision de calidad](../quality-approval.md).

## Interface
El fixture usa FIXTURE_TIMEOUT=5.0 para casos con descendientes, handshake de
marcadores reales y escrituras en un deadline monotonic absoluto del test.
assert_cancelled conserva su resultado y assertions de no supervivencia y tiempo.

## Invariants
Cumplir el [protocolo](../process-fixture-readiness.md). Los nueve metodos previos
y sus aserciones permanecen. No cambiar scripts/, workflows, workers, referencias
ni protecciones al autorar la propuesta. No aceptar un timeout inconcluso como
prueba de limpieza ni agregar skips/reintentos automaticos al oraculo.

## Examples
- Arranque retrasado 2 s: con fixture anterior falta readiness; con la nueva
  hay handshake y la contencion impide ambas escrituras tardias.
- Adaptador real sin contencion: el arranque se observa pero una escritura
  tardia hace fallar el caso.
- Objetivo no listo con deadline 1,5 s: sigue expirando dentro de deadline+gracia.

## Do / Don't
- DO: ejecutar hijo/nieto reales y distinguir el motivo de un rechazo.
- DON'T: aumentar la gracia de produccion ni quitar aserciones para obtener verde.

## Tests
tests/test_process_fixture_startup.py ejecuta el caso original con arranque
retrasado, el control negativo sin contencion y el deadline corto de lanzamiento.
No requiere SDK, Node ni red. Los intentos fallidos del CI se conservan.

## Constraints
Antes de adoptar/publicar este oraculo actualizado se requiere un nuevo baseline
humano explicito. PARAR y reportar si se necesita cambiar el runtime o alguna
otra asercion. El budget es declarativo; no se afirma Nivel 2 ni sandbox.
