---
type: 'Task Contract'
title: 'Cierre con aceptación desde KDD Board'
description: 'Iniciar la aceptación de una tarea Git desde Board y consultar su resultado con el recibo validado.'
tags: ['board', 'acceptance', 'git', 'evidence']
task: board-finish-acceptance
intent: 'Permitir un cierre verificable aunque la matriz dure más que una solicitud HTTP.'
target: tools/kdd-board/src/git-api.ts
language: typescript
signature: 'POST y GET /api/tasks/ID/acceptance'
test_command: 'node --test tools/kdd-board/tests/board-finish-acceptance.test.ts'
test_runner: node-test
test_scope: infrastructure
test_timeout: 180
tests: 'tools/kdd-board/tests/board-finish-acceptance.test.ts'
tests_sha256: '9c7ec8fedb2aae2cf22d1a837535c5167d8ceebee6536b70d2ee7bf9392be77d'
oracle_files: ['tools/kdd-board/tests/board-finish-acceptance.test.ts', 'tools/kdd-board/tests/project-fixture.ts', 'tests/fixtures/board_finish_acceptance.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py', 'tools/kdd-board/package.json', 'tools/kdd-board/package-lock.json']
touch_only: ['tools/kdd-board/src/git-api.ts', 'tools/kdd-board/src/git-task-store.ts', 'tools/kdd-board/src/git-bridge.ts', 'tools/kdd-board/src/task-acceptance.ts', 'tools/kdd-board/public/git-board.js', 'scripts/tasks.py', 'scripts/task_git.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
deps_allowed: ['node', 'python', 'git']
forbids: ['network-outside-board-loopback', 'llm', 'automatic-baseline-approval']
---

## Intent

El piloto TASK-006 comprobó el [cierre por CLI](task-finish-acceptance.md) y su [recibo en Board](board-test-evidence.md). Su matriz tardó 1.460,45 s. La transición ordinaria de Board devolvió HTTP 503 y la llamada al coordinador tiene un límite de 180 s. La aceptación necesita una solicitud de inicio corta y una consulta independiente de su resultado.

## Interface

- `GET /api/tasks/TASK-ID/acceptance` consulta el cierre con aceptación. Una tarea en curso sin ejecución registra `state: idle`, `task_id`, `tested_commit` observado en `main` y `approved_ref` de la tarea. Un intento devuelve esos datos, `run_id` y uno de `running`, `failed` o `done`.
- `POST /api/tasks/TASK-ID/acceptance` solicita la operación con el objeto `{tested_commit}`. El SHA debe ser completo y corresponder al `main` observado por el usuario. `retry: true` permite otra ejecución tras un fallo del mismo SHA. Se acepta HTTP 202 con `state: running` y el `run_id` sin esperar la matriz. Una solicitud repetida en curso devuelve el mismo identificador. Un cierre ya acreditado para el SHA pedido devuelve HTTP 200 con su resultado. Si cambió el candidato devolver HTTP 409 con `TASK_RACE`. Para una ejecución de otra tarea en curso, devolver HTTP 409 con `TASK_LOCK`.
- En `done`, devolver el `closed_commit` de la transición del diario y `receipt_sha256` vinculados al recibo que valida la [proyección de Board](board-test-evidence.md). En `failed`, devolver `error_code` comprobable, sin publicar salida libre del oráculo. Si se altera el recibo de un cierre, la consulta devuelve HTTP 409 con `TASK_EVIDENCE_INVALID`. Una consulta de estado jamás inicia una ejecución. Se aplica la autenticación Git de Board a las dos rutas.
- `tasks.py finish TASK-ID --verify-acceptance --expected-head SHA` añade una precondición al cierre delegado. El coordinador coteja el SHA exacto bajo su bloqueo Git antes de ejecutar la matriz. Si difiere, devuelve `TASK_RACE`. El CLI sin ese parámetro y las transiciones históricas conservan sus interfaces.
- En el panel Git de Board, la acción explícita «Verificar aceptación y cerrar» inicia la operación para el SHA mostrado. La vista vuelve a consultar la ejecución al abrir la tarea. El usuario puede consultar el estado durante el trabajo y abrir la evidencia cuando se confirme el cierre.

## Invariants

- Reutilizar el comando de aceptación de KDD con el contrato y la política de la referencia aprobada de la tarea. La solicitud HTTP fija el commit a comprobar y carece de campos para aprobar otro baseline, sustituir la política o elegir comandos.
- Ejecutar en segundo plano respecto de la solicitud HTTP y mantener los 180 s del cierre histórico de Board y los límites vigentes de las demás operaciones. Conservar la contención y los límites de cada obligación. Una sola ejecución de aceptación por repositorio puede estar en curso en este Board. La pérdida de la conexión del navegador deja la ejecución consultable mientras sigue activo Board.
- La tarea sigue `in_progress` hasta que el coordinador publica un único cierre Git. Antes de mostrar `done`, verificar con la proyección canónica que el recibo corresponde al mismo `tested_commit` y `approved_ref` y acredita ambas pasadas. El padre del cierre debe ser el commit probado. Ante un rechazo o una deriva de `main` detectada durante la matriz, devolver el resultado fallido y conservar el estado de la tarea.
- Un reintento explícito de un fallo sobre el mismo SHA registra un identificador nuevo. Repetir el inicio mientras hay una ejecución activa consulta la existente. La evidencia del cierre se sigue leyendo del diario Git.
- La ruta `PATCH /api/tasks/TASK-ID/status` conserva el cierre histórico, el resto de las transiciones y su forma de error. Los modelos de evidencia, las suites existentes, Ubuntu, Windows y las dos pasadas se conservan.

## Examples

- Al iniciar la aceptación de TASK-006, Board devuelve el identificador antes de recibir el primer resultado. Al reabrir la vista se consulta el mismo cierre. El recibo de `done` identifica el commit que se mostró al iniciarlo.
- Si el commit cambia durante la matriz, Board comunica `TASK_RACE`, la tarea sigue en curso y el intento no produce recibo.

## Do / Don't

Reutilizar el coordinador Git y el proyector de recibos existentes. Mostrar estado de la ejecución y estado de la tarea según sus fuentes canónicas.

## Tests

Usar HTTP de Board, un Git temporal y el CLI real de KDD. Un oráculo bloqueado por una señal de la prueba permite observar el inicio, la consulta y las solicitudes repetidas antes de que termine la matriz. Observar el lanzamiento real de Python para cotejar el SHA delegado y confirmar que el trabajador carece del temporizador de la solicitud. Verificar un recibo válido con dos pasadas, un fallo después de pasar el oráculo principal, reintento explícito, SHA inicial obsoleto, avance durante la ejecución, identidad errónea de aceptación aun con huella coincidente y cierre histórico. Un control cierra el mismo proyecto con el CLI vigente y comprueba el recibo en Board. Tras implementar, recorrer también la acción de la vista en Chromium sobre una copia del banco.

## Constraints

El piloto usa una instancia local de Board. El alcance probado de reanudación es volver a consultar desde otra solicitud mientras Board sigue activo. El cierre y su recibo se conservan en Git con el mecanismo de publicación del coordinador bajo su bloqueo. La prueba de concurrencia cubre el trabajo que respeta ese bloqueo y los avances de main durante la matriz. PARAR y reportar si se necesita cambiar oráculos existentes, ampliar el perímetro o modificar el runtime de CI.
