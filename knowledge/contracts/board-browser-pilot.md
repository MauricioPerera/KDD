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
oracle_files: ['tools/kdd-board/tests/browser-pilot-receipt.test.mjs', 'tools/kdd-board/tests/project-fixture.ts', 'tools/kdd-board/package-lock.json', 'tools/kdd-board/browser-pilot/package.json', 'tools/kdd-board/browser-pilot/package-lock.json', 'tools/kdd-board/browser-pilot/pins.json', 'tools/kdd-board/browser-pilot/e2e.config.mjs', 'tools/kdd-board/browser-pilot/tests/fixture.mjs', 'tools/kdd-board/browser-pilot/tests/handoff.e2e.ts', 'tools/kdd-board/browser-pilot/tests/pilot-live.test.mjs', 'tools/kdd-board/browser-pilot/tests/report-v1-pilot.json']
test_scope: infrastructure
test_timeout: 60
budget:
  cyclomatic_max: 14
  nesting_max: 4
  params_max: 4
tests: tools/kdd-board/tests/browser-pilot-receipt.test.mjs
tests_sha256: 'beb5983ac0c7516b9433e5177b3096d9474af08a8d7649ab781a763a755b719a'
touch_only: ['tools/kdd-board/browser-pilot/run.mjs', 'tools/kdd-board/browser-pilot/README.md', 'knowledge/board-git.md', '.github/workflows/board-browser-pilot.yml']
deps_allowed: ['node', 'python', 'git', 'e2e', '@e2e-dev/web']
forbids: ['llm']
---

## Intent

Acreditar el [relevo de revision](board-review-handoff.md) por navegador real con oraculo revisado. Mantenerlo optativo.

## Interface

`node tools/kdd-board/browser-pilot/run.mjs --approved-ref SHA --output DIR` ejecuta los dos casos sobre Board real en loopback. Escribe `receipt.json` y el `report.json` original en un directorio nuevo externo al checkout. El recibo registra `checkout`, `approved_ref`, `report_sha256`, `run_id`, `exit_code`, `ids`, `inputs` (rutas relativas a KDD y sus SHA-256) y `runtime` (pins verificados). `--verify-report --report RUTA --exit-code N [--previous-run-id ID]` verifica los campos de un reporte suministrado y su coherencia con esos argumentos. La frescura y el origen solo los acredita una ejecucion propia. Ambos modos devuelven JSON en stdout con `ok` y los IDs aceptados. Un rechazo devuelve JSON y codigo 1.

## Invariants

- Repositorio Git temporal con datos sinteticos y dos candidatos. Comprobar en el navegador el estado, los SHAs y la aprobacion pendiente, y comparar refs, indice y estado de trabajo del repositorio de tareas antes y despues de consultar ambos candidatos.
- La ejecucion real exige los pins de Node, paquetes y ejecutable Chromium. El verificador de reportes funciona con Node 24 del CI normal. Preparar fuera del checkout una raiz e2e aislada con salida nueva dentro de esa raiz. Los procesos del piloto reciben solo el entorno local necesario y datos sinteticos. Ejecutar con cero modelos, reintentos o filtros.
- Ejecutar codigo y oraculos del checkout identificado, sin cambios locales en los archivos ejecutados. Los oraculos coinciden con el baseline aprobado. Exigir salida real cero, estados y contadores coherentes de `report-1`, corrida distinta, exactamente los dos IDs previstos y un intento aprobado por ID. Guardar los hashes de config, manifiestos, locks, pins, fixture, escenario y oraculos. Ante una salida preexistente, rechazar sin escribir ni sobrescribir evidencia.
- Rechazar fallo real de la asercion, seleccion vacia y reporte verde anterior. Correr dos pasadas del mismo SHA en Ubuntu y Windows. Medir preparacion fria y ejecucion con navegador disponible. Conservar el CI principal, sus dos pasadas, cobertura, umbrales y protecciones.

## Examples

- Candidato listo muestra su SHA y solicita aprobacion humana. El segundo muestra su SHA y revision pendiente.
- Una seleccion vacia devuelve error aun cuando quede un reporte verde anterior.

## Do / Don't

DO aplicar aserciones exactas. Usar el MCP solo con datos sinteticos y revisar las lineas que genera.

## Tests

El `test_command` valida el recibo sin navegador. El oraculo optativo `node --test tools/kdd-board/browser-pilot/tests/pilot-live.test.mjs`, con `KDD_PILOT_APPROVED_REF` y los pins instalados, comprueba la entrada normal y usa las salidas autenticas de Chromium para rechazar un fallo de asercion y el reporte que dejo una seleccion vacia.

## Constraints

PARAR y reportar si falta el baseline revisado o la autorizacion del workflow remoto. Conservar casos y oraculos existentes.
