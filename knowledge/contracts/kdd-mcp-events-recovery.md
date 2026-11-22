---
type: 'Task Contract'
title: 'Recuperar la orquestacion KDD por eventos'
description: 'Reanudar un hilo tras guardar una respuesta y reconocer su reentrega.'
tags: ['kdd', 'mcp', 'events', 'recovery']
task: kdd-mcp-events-recovery
intent: 'Conservar la respuesta, la identidad del encargo y el punto de avance tras reiniciar.'
target: examples/mcp-events-kdd/run.mjs
language: javascript
signature: 'export async function run(argv, hooks = {})'
test_command: 'node --test examples/mcp-events-kdd/recovery.test.mjs'
budget:
  cyclomatic_max: 16
  nesting_max: 4
tests: examples/mcp-events-kdd/recovery.test.mjs
tests_sha256: 'f3cb491f25d1f4a2b861d5ce412564705d2b8dd2e1f09a25274092d6b8aa6afb'
touch_only: ['examples/mcp-events-kdd/run.mjs', 'examples/mcp-events-kdd/state.mjs', 'examples/mcp-events-kdd/delegation.mjs', 'examples/mcp-events-kdd/events.mjs', 'examples/mcp-events-kdd/candidate.py', 'examples/mcp-events-kdd/README.md']
deps_allowed: ['stdlib']
forbids: ['baseline-approval', 'polling']
---

## Intent

Hacer recuperable el traspaso del [piloto](../../examples/mcp-events-kdd/README.md)
sin cambiar el [flujo de aprobacion](../quality-approval.md).

## Interface

`--resume` reabre el estado del mismo informe, con el mismo checkout,
SHA base, origen del journal y propietario. El orquestador sigue las
notificaciones y recupera el journal desde el cursor guardado.

## Invariants

Una respuesta confirmada queda persistida con par, tarea, hilo y evento.
Reentregar el mismo evento conserva la respuesta y la transicion posterior.
Los reintentos de envio conservan el ID y el mensaje originales. Una sola
instancia puede escribir una ejecucion. El oraculo y los insumos protegidos
se comprueban al reanudar y antes de cerrar.

## Examples

- Interrumpir tras guardar la respuesta de ALPHA y volver a recibir su evento
  conserva el hilo y permite enviar una sola tarea a Goldfish.
- Si se pierde el recibo de un envio, la reanudacion usa el mismo ID de tarea.

## Do / Don't

- DO: conservar evidencias de la reentrega junto al resultado original.
- DON'T: sondear respuestas ni convertir un callback en aprobacion.

## Tests

El [oraculo local](../../examples/mcp-events-kdd/recovery.test.mjs) verifica
la reanudacion, la exclusividad y el envio idempotente. La prueba viva
complementa ese oraculo con un reinicio y una reentrega firmada.

## Constraints

PARAR y reportar si el checkout, los insumos o la identidad de la ejecucion
difieren del estado guardado. El cursor depende de la retencion del journal.
