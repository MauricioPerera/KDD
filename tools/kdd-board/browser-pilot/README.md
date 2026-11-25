# Relevo de revisión de KDD-Board en Chromium

El [contrato](../../../knowledge/contracts/board-browser-pilot.md) fija dos casos. Ambos usan un repositorio Git desechable y el Board real en loopback. El candidato con v1 presenta su SHA, el estado listo y la aprobación humana pendiente. El candidato sin v1 muestra su propio SHA y queda pendiente de revisión. La consulta conserva refs, índice, estado del diario y evidencia sintética.

## Preparar y ejecutar

Usa Node 24.16.0, Git y Python 3.11 con las actualizaciones de seguridad vigentes. Ejecuta desde la raíz de KDD. Usa un checkout que contenga el SHA completo del baseline aprobado y su historial. Puedes seleccionar Python con KDD_PYTHON.

```text
npm ci --prefix tools/kdd-board --ignore-scripts
npm ci --prefix tools/kdd-board/browser-pilot --ignore-scripts
node tools/kdd-board/browser-pilot/node_modules/playwright-core/cli.js install --only-shell chromium
```

En Ubuntu, si faltan bibliotecas del sistema, usa la misma CLI con
`install --with-deps --only-shell chromium`. El [manifiesto de pins](pins.json) fija el resto de las versiones. Para medir la preparación en frío, apunta PLAYWRIGHT_BROWSERS_PATH a un directorio vacío externo al checkout. Conserva esa ruta para medir la segunda pasada con el navegador preparado.

```text
node tools/kdd-board/browser-pilot/run.mjs --approved-ref SHA_COMPLETO --output RUTA_NUEVA_FUERA_DE_KDD
```

El destino debe tener un padre existente. Al aprobarse la ejecución contiene report.json y receipt.json. El recibo vincula los bytes del reporte, los IDs, el checkout y el baseline. También contiene el tiempo de Chromium en browser_ms, la huella del ejecutable y los hashes del estado Git consultado.

Para comprobar los campos del reporte por separado, pasa el status del proceso y, si lo conoces, el ID de la ejecución anterior. La procedencia y frescura las comprueba el comando que ejecuta Chromium.

```text
node tools/kdd-board/browser-pilot/run.mjs --verify-report --report RUTA_DEL_REPORTE --exit-code 0
node --test tools/kdd-board/tests/browser-pilot-receipt.test.mjs
```

Con KDD_PILOT_APPROVED_REF igual al SHA completo del baseline, el control optativo comprueba dos recibos frescos, el rechazo de un SHA sin oráculos y tres contramuestras. Chromium ejecuta una aserción fallida inducida al retirar un v1 sintético y una selección vacía que deja el reporte anterior intacto. El control también prueba que se rechaza un destino usado.

```text
node --test tools/kdd-board/browser-pilot/tests/pilot-live.test.mjs
```

## Proponer pasos con Goldfish

Prepara un proyecto e2e temporal y entrega al Goldfish solo el contrato, el SHA y el descriptor de la instancia sintética. Usa el e2e del lock para iniciar el MCP stdio, con una sesión nueva acotada a esa instancia.

```text
node RUTA_DEL_PILOTO/node_modules/e2e/dist/cli/bin.js mcp --config e2e.config.mjs --max-sessions 1
```

Con open_session, navega en el Board sintético y observa cada pantalla antes de usar el identificador de un control. Pide test_lines al terminar y cierra la sesión. El borrador comprobado puede incluir la URL de inicio con el fragmento de autenticación sintético. Usa datos sintéticos, sanea el borrador y revisa los selectores semánticos.

Añade aserciones de estado, SHA y disponibilidad de los controles, y verifica la conservación del diario. Prueba ambos casos y las contramuestras. Incluye el oráculo final y sus dependencias en el baseline sujeto a revisión humana. El piloto ejecuta las aserciones selladas sin modelos ni reintentos.
