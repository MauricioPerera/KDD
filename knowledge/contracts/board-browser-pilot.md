---
type: 'Task Contract'
title: 'Piloto Chromium del relevo de Board'
description: 'Verifica la vista real y un recibo fresco de dos casos deterministas.'
tags: ['board', 'browser', 'review', 'integration']
task: board-browser-pilot
intent: 'Comprobar el relevo visible y la identidad de cada ejecucion.'
target: tools/kdd-board/browser-pilot/run.mjs
language: javascript
signature: 'node tools/kdd-board/browser-pilot/run.mjs'
test_command: 'node --test tools/kdd-board/tests/browser-pilot-receipt.test.mjs'
test_runner: node-test
oracle_files: ['tools/kdd-board/tests/browser-pilot-receipt.test.mjs', 'tools/kdd-board/tests/project-fixture.ts', 'tools/kdd-board/package-lock.json', 'tools/kdd-board/browser-pilot/package.json', 'tools/kdd-board/browser-pilot/package-lock.json', 'tools/kdd-board/browser-pilot/pins.json', 'tools/kdd-board/browser-pilot/e2e.config.mjs', 'tools/kdd-board/browser-pilot/tests/fixture.mjs', 'tools/kdd-board/browser-pilot/tests/handoff.e2e.ts', 'tools/kdd-board/browser-pilot/tests/report-v1-pilot.json']
test_scope: infrastructure
test_timeout: 60
budget:
  cyclomatic_max: 14
  nesting_max: 4
  params_max: 4
tests: tools/kdd-board/tests/browser-pilot-receipt.test.mjs
tests_sha256: 'ac657734acd2b902f73969c636fc59fe97582c45cbde8ba8df8ec66c91cc10f8'
touch_only: ['tools/kdd-board/browser-pilot/run.mjs', 'tools/kdd-board/browser-pilot/README.md', 'knowledge/board-git.md', '.github/workflows/board-browser-pilot.yml']
deps_allowed: ['node', 'python', 'git', 'e2e', '@e2e-dev/web']
forbids: ['llm']
---

## Intent

Acreditar el [relevo de revision](board-review-handoff.md) por navegador real con oraculo revisado. Mantenerlo optativo.

## Interface

`node tools/kdd-board/browser-pilot/run.mjs --approved-ref SHA --output DIR` ejecuta los dos casos sobre Board real en loopback. Escribe un recibo en un directorio nuevo externo al checkout. `--verify-report --report RUTA --exit-code N [--previous-run-id ID]` aplica el mismo criterio de aceptacion al reporte externo. Devuelve JSON en stdout con `ok` y los IDs aceptados. Un rechazo devuelve JSON y codigo 1.

## Invariants

- Repositorio Git temporal con datos sinteticos y dos candidatos. Comprobar desde el navegador listo y pendiente, SHAs completos, aprobacion humana pendiente y ausencia de cambios en el diario de la tarea.
- Fijar Node, e2e, motor web, lock y revision Chromium. Aislar la instalacion. Ejecutar con cero modelos, reintentos o filtros en el caso aceptado.
- Exigir salida real cero, campos de evidencia validos de `report-1`, corrida distinta y directorio sin reporte previo, exactamente los dos IDs previstos ejecutados con un intento aprobado, sin omisiones, errores generales, flakes ni uso de modelos. En una ejecucion exitosa vincular el reporte original al checkout y baseline exactos, config, lock, revision y hashes.
- Rechazar fallo real de la asercion, seleccion vacia y reporte verde anterior. Correr dos pasadas del mismo SHA en Ubuntu y Windows. Medir preparacion fria y ejecucion con navegador disponible. Conservar el CI principal, sus dos pasadas, cobertura, umbrales y protecciones.

## Examples

- Candidato listo muestra su SHA y solicita aprobacion humana. El segundo muestra su SHA y revision pendiente.
- Una seleccion vacia devuelve error aun cuando quede un reporte verde anterior.

## Do / Don't

DO aplicar aserciones exactas. Usar el MCP solo con datos sinteticos y revisar las lineas que genera.

## Tests

Ejecutar un oraculo del recibo por CLI y la suite de Chromium usando el servidor de KDD-Board y Git reales. La prueba basica del recibo es independiente de una instalacion de Chromium.

## Constraints

PARAR y reportar si falta el baseline revisado o la autorizacion del workflow remoto. Conservar casos y oraculos existentes.
