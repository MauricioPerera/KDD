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
test_runner: node-test
test_command: 'node --test examples/mcp-events-kdd/recovery.test.mjs'
budget:
  cyclomatic_max: 16
  nesting_max: 4
tests: examples/mcp-events-kdd/recovery.test.mjs
oracle_files: ['examples/mcp-events-kdd/recovery.test.mjs', 'examples/mcp-events-kdd/recovery-checkpoint.mjs']
tests_sha256: 'a26408c5e43d67c3e6c152ac70f4178ec790dd88b0feae8106abdc119a0e94c6'
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
Una notificacion duplicada no satisface la espera de una respuesta nueva.
Al reanudar, el lector conserva el cursor y abre un solo encargo a Goldfish.
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
la exclusividad y el envio idempotente. Tambien reabre SQLite tras terminar
un proceso real e introduce la reentrega por el lector de journal, con
transporte simulado y un solo envio a Goldfish. La prueba viva
complementa ese oraculo con un reinicio y una reentrega firmada.

## Constraints

PARAR y reportar si el checkout, los insumos o la identidad de la ejecucion
difieren del estado guardado. El cursor depende de la retencion del journal.
