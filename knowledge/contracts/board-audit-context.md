---
type: 'Task Contract'
title: 'Resguardar Board ante cambios de contexto y datos invalidos'
description: 'Evitar escrituras inseguras y conservar la ultima vista valida.'
tags: ['board', 'git', 'security', 'integration']
task: board-audit-context
intent: 'Rechazar cambios de contexto inseguros y datos inconsistentes sin perder tareas.'
target: tools/kdd-board/src/server.ts
language: typescript
signature: 'createServer(apiToken)'
test_command: 'python -m unittest tests/test_board_audit_context.py'
budget:
  cyclomatic_max: 20
  nesting_max: 5
  lines_max: 250
  params_max: 5
tests: tests/test_board_audit_context.py
tests_sha256: '83c61968723ff2b9a294ae89aaabbd3360eae4ea0db58d2ff98dd0143029c012'
touch_only: ['tools/kdd-board/src/server.ts', 'tools/kdd-board/src/task-store.ts', 'tools/kdd-board/public/app.js']
deps_allowed: ['node', 'git', 'zod', 'fastwebmcp']
forbids: ['llm']
---

## Intent
Complementar el [vault](board-vault-isolation.md) y la [recuperacion](board-polling-recovery.md)
con controles ante cambios de repositorio y datos legacy inconsistentes.

## Interface
Si se crea un repositorio despues de abrir un Board legacy, bloquear las escrituras
legacy con un error accionable que solicite reiniciar. En un Git existente, no
aceptar exclusiones aportadas solo por configuracion efimera heredada del proceso.
Una exclusion persistente valida permite el vault. No crear ni modificar reglas Git.

## Invariants
Preservar el uso normal fuera de Git. Los IDs duplicados del almacenamiento
legacy se rechazan sin reescribir sus bytes. Una respuesta de tareas con campos
anidados invalidos conserva lista y columnas previas, informa el error y se
recupera al recibir datos validos. Los valores del vault no salen en respuestas.
Conservar la exclusion, indexacion y concurrencia del vault ya contratado.

## Examples
- Inicializar Git con Board abierto impide crear tareas legacy y guardar el vault.
- Un Git sin exclusiones persistentes rechaza credenciales aunque el proceso
  reciba core.excludesfile por variables de configuracion temporales o un
  archivo global seleccionado solo mediante variables del proceso.
- Cumplir un requerimiento de una tarea inexistente tras inicializar Git no
  puede escribir un vault ni dejar credenciales fuera de las exclusiones.
- Dos IDs identicos no se reducen silenciosamente a una sola tarea.
- Un requirements que es texto no borra la tarjeta mostrada anteriormente.

## Do / Don't
- DO: ejecutar HTTP autenticado y Git reales sobre directorios temporales.
- DON'T: resolver la transicion escribiendo secretos, alterando Git o perdiendo datos.

## Tests
El oraculo Python sella el helper Node, que prueba los casos anteriores y controles
positivos con Git real; la interfaz usa HTTP y DOM simulado, no navegador visual.
Una copia Python inicializada sin dependencias de Board omite explicitamente este
control. La plantilla completa exige las dependencias y no permite omitirlo.

## Constraints
Conservar Ubuntu/Windows, cobertura y dos pasadas. PARAR y reportar si se necesita
modificar oraculos previos sin revision, runtime o protecciones sin autorizacion.
