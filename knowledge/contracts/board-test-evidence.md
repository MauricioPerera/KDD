---
type: 'Task Contract'
title: 'Visor de evidencia de pruebas en KDD Board'
description: 'Consultar recibos Git y el piloto Chromium con identidad y alcance explicitos.'
tags: ['board', 'evidence', 'git', 'ui']
task: board-test-evidence
intent: 'Mostrar que prueba se ejecuto, su revision y la evidencia que la respalda.'
target: tools/kdd-board/src/git-api.ts
language: typescript
signature: 'GET /api/tasks/ID/evidence, GET /api/board/evidence/browser-pilot'
test_command: 'node --test tools/kdd-board/tests/board-test-evidence.test.ts'
test_runner: node-test
test_scope: infrastructure
test_timeout: 180
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tools/kdd-board/tests/board-test-evidence.test.ts'
tests_sha256: 'ce060a124873b245299a6b98d25e2dff821e75ea042a5120ffac5760aa3cee29'
oracle_files: ['tools/kdd-board/tests/board-test-evidence.test.ts', 'tools/kdd-board/tests/project-fixture.ts', 'tools/kdd-board/package.json', 'tools/kdd-board/package-lock.json', 'tools/kdd-board/tests/fixtures/board-evidence/.gitattributes', 'tools/kdd-board/tests/fixtures/board-evidence/receipt.json', 'tools/kdd-board/tests/fixtures/board-evidence/report.json', 'tools/kdd-board/browser-pilot/tests/evidence-browser.test.mjs', 'tools/kdd-board/browser-pilot/package.json', 'tools/kdd-board/browser-pilot/package-lock.json', 'tools/kdd-board/browser-pilot/pins.json']
touch_only: ['scripts/board_test_evidence.py', 'tools/kdd-board/src/git-task-store.ts', 'tools/kdd-board/src/git-api.ts', 'tools/kdd-board/src/browser-evidence.ts', 'tools/kdd-board/public/git-board.js', 'tools/kdd-board/public/app.js', 'tools/kdd-board/public/index.html', 'tools/kdd-board/public/style.css', 'tools/kdd-board/browser-pilot/README.md']
deps_allowed: ['node', 'python', 'git']
forbids: ['network', 'llm']
---

## Intent

Abrir la [evidencia de Task v1](../data_models/git-task.md) y los casos del
[piloto Chromium](board-browser-pilot.md) desde Board.

## Interface

Dos lecturas autenticadas. La de tarea devuelve `status`, `task_id` y
`observed_commit`. Disponible agrega `approved_ref`, `tested_commit`,
`artifact: {path, sha256}` y `receipt: {version, runner, total, granularity, files}`.
`files` usa objetos `{path, executed, skipped, ok}`. El piloto se configura con
`KDD_BOARD_BROWSER_EVIDENCE_DIR` y `KDD_BOARD_BROWSER_EVIDENCE_PIN` (SHA del
checkout, dos puntos, SHA-256 de receipt.json). Sin configuracion devuelve
`unavailable`. Devuelve estado, procedencia
`local_bundle`, identidad del recibo y casos con ID, resultado, duracion y adjuntos.

## Invariants

- Leer objetos originales de un commit de main. Verificar nombre, identidad,
  SHA y huella con el validador de tareas. Pendiente, inexistente e invalido
  son estados distintos. La huella es la del recibo canonico de Task v1.
  Ocultar stdout y stderr en la respuesta.
- v1 muestra total de ejecucion, v2 conteo por archivo. Mostrar como no
  disponible el detalle que el recibo no registra.
- El operador fija el SHA del checkout y el hash de los bytes originales
  de receipt.json. El visor comprueba los commits en el repositorio de Board
  y la ascendencia del baseline. Coteja pin, hash, ID y casos con el verificador original.
  El verificador recibe una copia
  temporal privada de los mismos bytes cotejados. Retirar la copia al salir.
  Mostrar los casos del piloto de Board en un panel independiente del proyecto
  seleccionado. El pin acredita concordancia
  con la fuente seleccionada por el operador. Conservar los hashes de entradas
  dentro del recibo fijado, medidos sobre los bytes de su entorno original.
  Proyectar solo identidad del reporte y datos de caso, sin pasos ni logs.
  Admitir las listas vacias de adjuntos en intentos y pasos de este piloto. El recibo Git y el
  reporte Chromium corresponden a sus ejecuciones completas.
- El detalle Git abre Evidencia por tarea con SHA, runner, conteo y nivel de
  detalle. El panel Chromium muestra la procedencia local, la huella del
  reporte y una fila por caso con resultado, numero y duracion del intento. Ausencia
  de adjuntos se indica por caso.
- Configurar una carpeta directa y archivos regulares. Rechazar enlaces en
  esa carpeta o sus dos entradas. No acceder a red, descargar adjuntos ni
  escribir refs, indice, evidencia o aprobaciones al consultar. Mostrar texto.

## Examples

- Un cierre v2 validado muestra su archivo y el conteo real.
- Un reporte con digest distinto devuelve conflicto y carece de casos.

## Do / Don't

DO conservar los recibos, el piloto optativo y las dos pasadas vigentes.

## Tests

Git y HTTP reales, cierre historico v1, cierre v2 instrumentado y paquete
capturado del piloto Chromium real. Prueba optativa del visor con el Chromium
fijado: `node --test tools/kdd-board/browser-pilot/tests/evidence-browser.test.mjs`.
Ejecutarla para verificar la entrega visual del piloto en ambos sistemas.

## Constraints

- PARAR y reportar si se necesita cambiar oraculos previos, workflows o runtime.
