---
type: 'Task Contract'
title: 'Verificacion honesta del tablero'
description: 'Imponer evidencia y acceso local autenticado en KDD Board.'
tags: ['ccdd', 'security']
task: board-hardening
intent: 'Endurecer la frontera de verificacion del tablero local.'
target: tools/kdd-board/src/task-store.ts
language: typescript
signature: 'updateTaskStatus(id, newStatus, comment)'
test_command: 'node --test tools/kdd-board/tests/hardening.test.ts'
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: 'tools/kdd-board/tests/hardening.test.ts'
tests_sha256: 'b503e8737c2d952d95d1d80b410d3a0cd9bb5e762f3b107528b93a83871cf4dc'
touch_only: ['tools/kdd-board/src/*', 'tools/kdd-board/public/app.js', 'tools/kdd-board/tests/task-store.test.ts', 'tools/kdd-board/tests/webmcp-bridge.test.ts', 'tools/kdd-board/tests/http-hardening.test.ts', 'tools/kdd-board/package.json', '.github/workflows/validate.yml', '.gitignore', 'README.md']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
Aplicar la [validacion](../validacion.md) a la evidencia local del tablero.

## Interface
`updateTaskStatus(id, newStatus, comment)` rechaza cierre sin evidencia.

## Invariants
- No inventar tests ejecutados.
- Rechazar estados desconocidos y cierre sin evidencia vigente.
- HTTP requiere autenticacion y mismo origen; bind a loopback.
- HTTP y MCP ejecutan sobre el mismo proyecto y contrato validado.

## Examples
- Tarea sin evidencia -> rechazo de done.
- echo sin tests -> cero tests reconocidos.

## Do / Don't
- DO: preservar salida real con redaccion de valores conocidos.
- DON'T: prometer aislamiento frente a codigo hostil.

## Tests
Regresiones selladas antes de implementar; integracion HTTP adicional.

## Constraints
- PARAR y reportar si se requiere exponer el servicio publicamente.
