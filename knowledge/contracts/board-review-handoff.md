---
type: 'Task Contract'
title: 'Relevo de revision por candidato en KDD-Board'
description: 'Consultar desde una tarea Git la revision local del SHA seleccionado y sus antecedentes.'
tags: ['review', 'baseline', 'git', 'kdd-board']
task: board-review-handoff
intent: 'Retomar una revision con el ID de tarea y evidencia vinculada al SHA exacto.'
target: tools/kdd-board/src/git-api.ts
language: typescript
signature: 'GET /api/tasks/TASK-ID/review-handoff'
test_command: 'node --test tools/kdd-board/tests/review-handoff.test.ts'
test_runner: node-test
test_scope: infrastructure
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 5
tests: tools/kdd-board/tests/review-handoff.test.ts
tests_sha256: 'ecaddac29c86c35e22296981fa7e17a6bd96e47090f3adfab07b9c889c5ac332'
oracle_files: ['tools/kdd-board/tests/review-handoff.test.ts', 'tools/kdd-board/tests/project-fixture.ts', 'tools/kdd-board/package-lock.json']
touch_only: ['tools/kdd-board/src/git-api.ts', 'tools/kdd-board/src/git-task-store.ts', 'tools/kdd-board/public/git-board.js', 'scripts/board_review_handoff.py', 'knowledge/board-git.md']
deps_allowed: ['node', 'python', 'git']
forbids: ['llm']
---

## Intent

Aplicar el [relevo efimero](../delegacion-efimera-goldfish.md) a la
[vista Git](../board-git.md). Reusar la [revision v1](baseline-risk-review.md).

## Interface

El operador prepara `.agents/logs/board-reviews/TASK-ID/` en el proyecto.
`selection.json` contiene solo `current` y `previous`. Cada entrada identifica
`base_commit` y `candidate_commit` con los OID completos de Git. `previous`
es una lista ordenada con hasta ocho candidatos distintos; no incluye al actual.
Cada revision usa los bytes originales del v1 en `<candidate_commit>.json`.

GET autenticado, solo para una tarea existente en modo Git, devuelve
`task_id`, `approved_ref`, `evidence`, `current` y `previous`. La aprobacion
y la evidencia provienen del diario, o son null si faltan. Cada candidato
incluye `base_commit`, `candidate_commit`, `candidate_tree`, `review_status`
(`missing`, `blocked`, `ready`), `review_sha256` (null si no hay v1) y
`finding_codes`. Si falta la seleccion, el GET devuelve `current: null` y una
lista anterior vacia. Si falta el v1 actual, el SHA y su arbol se cotejan con
Git y el estado es `missing`. Un antecedente sin su v1 es invalido.

## Invariants

- Validar cada archivo v1 con el verificador existente y los dos SHA elegidos.
  Decodificar UTF-8 estricto y calcular la huella sobre los mismos bytes, incluso
  con CRLF. Consultar objetos locales de Git; prohibir descargas implicitas en
  un clon parcial. Si falta un objeto necesario, rechazar la consulta.
  `ready` indica revision lista. Solo el `approved_ref` canonico acredita
  una aprobacion para la tarea, y se muestra por separado.
- Un cambio de SHA exige evidencia vinculada al candidato nuevo incluso si
  conserva el arbol. Conservar los anteriores. Una reutilizacion requiere un
  v1 valido del nuevo SHA por el flujo de revision existente.
- Leer JSON UTF-8 de hasta 256 KiB por archivo, con claves unicas. Aceptar
  solo los archivos regulares del directorio fijo, sin symlinks, junctions
  ni hardlinks. Los datos invalidos dan 409 `REVIEW_HANDOFF_INVALID` sin
  exponer rutas absolutas, texto privado de reviews o diagnosticos
  internos. Una tarea inexistente sigue dando 404.
- La vista consulta por boton en el detalle Git y muestra estado, SHA,
  huella y antecedentes como datos. El refresco ordinario del mismo detalle
  conserva el resultado o error sin otra consulta. Una respuesta tardia nunca
  se muestra en otra tarea. El boton permite consultar de nuevo.
  No sondear, invocar revisores, aprobar el baseline ni escribir archivos,
  indices o refs. Conservar los endpoints, tools y transiciones existentes.

## Examples

- Un segundo proceso Board relee el mismo TASK-ID y devuelve el mismo SHA,
  arbol, dictamen y hash de los bytes originales.
- Seleccionar B, aun con el arbol de A, muestra B pendiente y A en el historial.
- Copiar el v1 de A a la ruta de B produce un rechazo y no lo declara listo.

## Do / Don't

DO verificar el flujo con HTTP, procesos y Git reales. No cargar el contenido
de archivos del candidato o del VPS en la respuesta del tablero.

## Tests

Comprobar reinicio, cambio de SHA, evidencia incompleta, auth, ausencia de
efectos y render del script de Board usando las respuestas reales. Comprobar
que un checkout distinto no sustituye la aprobacion ni la evidencia del diario.

## Constraints

PARAR y reportar si falta la revision del baseline antes de implementar. Mantener Ubuntu,
Windows, ambas pasadas, cobertura en la primera y la ventana de post-init.
La carpeta local es preparada por el operador. El piloto no importa archivos
desde chats, red o el checkout candidato ni modifica workflows.
