---
type: 'Task Contract'
title: 'Errores de dominio por WebMCP'
description: 'Preservar codigos y contexto de rechazos sin excepciones opacas del navegador.'
tags: ['quality', 'maintenance', 'verification']
task: board-webmcp-errors
intent: 'Preservar codigos y contexto de rechazos sin excepciones opacas del navegador.'
target: tools/kdd-board/public/app.js
language: javascript
signature: 'registerWebMcpTools()'
test_command: 'node --test tools/kdd-board/tests/structured-errors.test.ts'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tools/kdd-board/tests/structured-errors.test.ts
tests_sha256: '61f6b164b772900753f4c2d3e40d44ebb91352bfb6885ea85eaf79b21c4f33a5'
touch_only: ['tools/kdd-board/public/app.js', 'tools/kdd-board/src/git-task-store.ts', 'tools/kdd-board/src/git-bridge.ts', 'tools/kdd-board/src/git-api.ts']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Exito compatible; HTTP conserva error string y agrega code/status/details. WebMCP devuelve envelope isError con datos seguros. Dependencias pendientes reales; ningun efecto Git en rechazo.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- Iniciar tarea con dependencia abierta -> TASK_DEPENDENCIES y pending_dependencies.
- Error interno -> mensaje seguro, sin stack, token ni proceso o entorno.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tools/kdd-board/tests/structured-errors.test.ts. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
