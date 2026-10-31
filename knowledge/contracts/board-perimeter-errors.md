---
type: 'Task Contract'
title: 'Rechazo de perimetro coherente en las interfaces'
description: 'Conservar el error seguro de perimetro del coordinador por Store, HTTP y herramientas WebMCP registradas sin publicar un cierre.'
tags: ['board', 'tasks', 'governance', 'integration']
task: board-perimeter-errors
intent: 'Propagar TASK_PERIMETER como rechazo de dominio en las interfaces existentes.'
target: tools/kdd-board/src/git-task-store.ts
language: typescript
signature: 'GitTaskStore.transition(id, input)'
test_command: 'node --test tools/kdd-board/tests/perimeter-interface.test.ts'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tools/kdd-board/tests/perimeter-interface.test.ts
tests_sha256: '8d5269c920649658dc500268a69ecbcee3ba2be1285e0e4737b44627e14f47bf'
touch_only: ['tools/kdd-board/src/git-task-store.ts']
deps_allowed: ['node', 'zod', 'fastwebmcp']
forbids: ['llm', 'network']
---

## Intent

Aplicar la [matriz de controles e interfaces](../operation-controls.md),
conservando el [diario Git](board-git-journal.md) y los
[errores seguros](board-webmcp-errors.md).

## Interface

Conservar API y envelopes actuales. Un rechazo TASK_PERIMETER del coordinador
es un error de dominio 409. Los errores desconocidos siguen siendo 503 seguros.

## Invariants

- Store, HTTP autenticado y WebMCP registrado conservan TASK_PERIMETER y 409.
- El registro real del JavaScript cliente conserva la misma causa por HTTP.
- No publicar cierre, modificar Git ni ejecutar el oraculo antes del rechazo.
- No filtrar stderr, stack, rutas internas ni secretos como mensaje seguro.
- Un cierre permitido mantiene su evidencia real; un error interno sigue 503.

## Examples

- Implementacion con outside.txt -> TASK_PERIMETER, 409, sin cierre.
- Cambio permitido -> done con oraculo real y recibo de perimetro.
- Excepcion interna -> TASK_UNAVAILABLE, 503, sin informacion privada.

## Do / Don't

- DO conservar la separacion entre errores de dominio y fallos internos.
- DON'T convertir cualquier codigo recibido en error publico o duplicar reglas
  de perimetro en TypeScript.

## Tests

Oraculo nuevo tools/kdd-board/tests/perimeter-interface.test.ts. Usa Git real,
HTTP local real, registro de herramientas WebMCP y JavaScript cliente en VM.
No es una prueba de navegador real ni revision visual. Reutiliza sin editar
project-fixture.ts y los modulos anteriores de interfaces y cliente.

## Constraints

PARAR y reportar si se necesita otra fuente, editar una prueba anterior,
cambiar contratos congelados, ampliar budgets o modificar workflows/protecciones.
No implementar antes de aprobar el baseline nuevo; no cambiar dependencias.
