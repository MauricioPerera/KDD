---
type: 'Task Contract'
title: 'Corregir las fronteras de entrada del tablero'
description: 'Protege los datos HTTP y persistidos, los requisitos humanos, los formularios activos y los estados de verificacion.'
tags: ['ccdd', 'security', 'board']
task: board-audit-improvements
intent: 'Corregir los hallazgos de la auditoria del tablero local.'
target: tools/kdd-board/src/server.ts
signature: 'export function createServer(apiToken?: string)'
test_command: 'node --test tools/kdd-board/tests/audit-improvements.test.ts'
budget:
  cyclomatic_max: 30
  nesting_max: 6
tests: tools/kdd-board/tests/audit-improvements.test.ts
tests_sha256: 6015a9a0f5f4688184c52643dc8f23db4e61dc64cf8d5f387eaddf6ab9e9381d
touch_only: ['tools/kdd-board/src/*', 'tools/kdd-board/public/app.js', 'tools/kdd-board/tests/task-store.test.ts', 'tools/kdd-board/tests/webmcp-bridge.test.ts']
deps_allowed: ['zod', 'fastwebmcp']
forbids: ['llm']
---

## Intent
Aplicar las fronteras de confianza de [las garantias de verificacion](../verification-guarantees.md) a todas las entradas del tablero.

## Interface
Conservar las rutas HTTP y las herramientas WebMCP. Las entradas invalidas reciben HTTP 400 antes de mutar datos.

## Invariants
- Ningun dato recibido se convierte en un handler JavaScript.
- Un requisito secreto satisfecho tiene una credencial guardada.
- El refresco conserva el input activo, su valor y su seleccion sin persistir borradores.
- PASS requiere pruebas reconocidas; los demas resultados distinguen FAIL, SKIP y TIMEOUT.

## Examples
- isSecret como string -> HTTP 400.
- Requisito secreto sin valor -> HTTP 400 y tarea bloqueada.
- Refresco con formulario activo -> mismo input y valor.

## Do / Don't
- DO validar en runtime y comprobar el vault antes de marcar un requisito.
- DON'T guardar borradores secretos en sessionStorage o localStorage.

## Tests
El oraculo sellado cubre HTTP real, almacenamiento malformado, ejecucion real de tests y render en DOM simulado. La suite existente del tablero sigue obligatoria.

## Constraints
- PARAR y reportar si una correccion exige exponer credenciales.
- No publicar ni desplegar cambios.
