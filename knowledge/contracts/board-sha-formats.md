---
type: 'Task Contract'
title: 'SHA nativos en Store, transportes y formularios de Board'
description: 'Conservar aprobaciones y respuestas de commits SHA-1 y SHA-256 a traves del tablero.'
tags: ['board', 'git', 'integration']
task: board-sha-formats
intent: 'Alinear los formatos Git de Board con el coordinador canonico.'
target: tools/kdd-board/src/git-task-store.ts
language: typescript
signature: 'GitTaskStore(projectDir)'
test_command: 'node --test tools/kdd-board/tests/git-sha-formats.test.ts'
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 140
  params_max: 5
tests: tools/kdd-board/tests/git-sha-formats.test.ts
tests_sha256: '49aa793655b7189b7818df0561c738c3ce8a80e9e25d43d40b16218356e2d7dc'
touch_only: ['tools/kdd-board/src/git-task-store.ts', 'tools/kdd-board/src/git-bridge.ts', 'tools/kdd-board/public/git-board.js']
deps_allowed: ['node', 'zod', 'fastwebmcp']
forbids: ['network', 'llm']
---

## Intent
Cumplir los [formatos del tablero](../audit-remediation-approval-mutation-board.md)
y la [delegacion canonica](../board-git.md).
## Interface
Conservar Store, HTTP/WebMCP y formularios. SHA completo puede tener 40 o 64
hexadecimales; el coordinador verifica la identidad nativa de la aprobacion.
## Invariants
- Conservar sin truncar SHA aprobado, commit y evidencia de ambos formatos.
- Formularios aceptan ambos; un commit valido de 64 permite refrescar una vez.
- Rechazos mantienen estado y Git; no elegir HEAD ni ocultar errores de coordinador.
- Conservar autenticacion, esquemas estrictos y flujo/lecturas SHA-1 existente.
## Examples
- Repo SHA-256 real -> crear/preparar/iniciar/cerrar con evidencia e historial.
- Respuesta de commit invalida -> error visible, cero confirmaciones.
## Do / Don't
- DO: Git real y protocolos; diferenciar DOM controlado de navegador real.
- DON'T: usar solo strings de 64 caracteres como prueba del flujo Git.
## Tests
Oraculo Node nuevo con flujos Git SHA-1/SHA-256, HTTP, WebMCP, formularios y
respuestas; Node24 y dependencias fijadas existentes.
## Constraints
PARAR y reportar si requiere cambiar oraculos anteriores, runtime, dependencias,
workflow o proteccion. Baseline humano antes de implementar.
