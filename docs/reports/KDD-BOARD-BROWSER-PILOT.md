# Piloto Chromium para el relevo de revisión en KDD-Board

Verificado el 25 de noviembre de 2026 en el PR #221. La medición corresponde al candidato `b23b941f209ec4297cecfb05e1e8073e0ff0001f`. El PR se fusionó en `main` con sus seis commits en `4b63be53d61cc7e0765b464169b213cea7f02fec`, con el mismo árbol verificado. [PR #221](https://github.com/MauricioPerera/KDD/pull/221) · [CI de la fusión](https://github.com/MauricioPerera/KDD/actions/runs/45634751803)

## Qué aporta a KDD

El piloto prueba la consulta del [relevo de revisión](../../knowledge/contracts/board-review-handoff.md) desde Chromium contra Board real en loopback. El fixture crea tareas y commits Git reales en un proyecto desechable. Los casos comprueban el SHA completo y el control **Consultar revisión**. El candidato con v1 aparece listo y conserva la aprobación humana pendiente. El candidato sin v1 queda pendiente de revisión. El control de integración compara refs, índice, estado de trabajo y bytes de la evidencia antes y después de la consulta. [Contrato del piloto](../../knowledge/contracts/board-browser-pilot.md)

Chromium se instala para el workflow optativo. El CI habitual ejecuta las 25 pruebas del recibo con Node. Ese control también pasó en un clon sin `node_modules`. Las cuatro integraciones optativas ejercitan la CLI real, sus dos recibos frescos y los rechazos. [Guía operativa e instalación](https://github.com/MauricioPerera/KDD/blob/b23b941f209ec4297cecfb05e1e8073e0ff0001f/tools/kdd-board/browser-pilot/README.md)

## Contrato, código y revisión

| Referencia | Qué identifica |
| --- | --- |
| `7c8d3b9529e311657ba7bab00d85f7a99dc93f98` | Base de `main` al abrir el PR. |
| `467deac32c22b5df3d64275a0cfd4078ba4d06ac` | Baseline de contratos y oráculos. Dos Goldfish revisaron el SHA antes de la aprobación humana y la implementación. |
| `b23b941f209ec4297cecfb05e1e8073e0ff0001f` | Candidato de seis commits ejecutado por el piloto en ambos sistemas. |
| `64dcd8ecbdbb5f2c5f8e2da2ec2a215da0e6031b` | Checkout de merge que ejecutó el CI habitual. Comparte con el candidato el árbol `955bdc931e9631e294195ca709e2d371b90559e9`. |

El workflow nuevo se revisó por separado con la base, el árbol y el blob exactos. El registro añadió la entrada del árbol, conservó las 129 anteriores y restauró la revisión protegida temporal después del guard. Continúan vigentes los cinco checks requeridos del CI habitual. [Ejecución de `trusted-pr-gate`](https://github.com/MauricioPerera/KDD/actions/runs/45625522609)

## Las cuatro pasadas del piloto

Se fijaron Node `24.16.0`, e2e y su núcleo `0.24.0`, motor web `0.16.1`, Playwright Core `1.65.1` y Chromium Headless Shell `159.0.8154.6`, revisión `1255`. Cada pasada del intento 1 ejecutó los mismos dos IDs con un intento aprobado por caso, cero llamadas a modelos y cero omisiones. Se cotejaron la salida real de Chromium, el esquema `report-1`, los 13 hashes de entrada contra Git y el SHA-256 de cada reporte. [Pins](https://github.com/MauricioPerera/KDD/blob/b23b941f209ec4297cecfb05e1e8073e0ff0001f/tools/kdd-board/browser-pilot/pins.json) · [Ejecución del piloto](https://github.com/MauricioPerera/KDD/actions/runs/45625522872)

| Sistema | Caché de Chromium | Preparación | Lanzador completo |
| --- | --- | ---: | ---: |
| Ubuntu | Vacía | 4,08 s | 3,81 s |
| Ubuntu | Con navegador | 0,31 s | 3,58 s |
| Windows | Vacía | 3,86 s | 8,91 s |
| Windows | Con navegador | 0,25 s | 6,68 s |

La preparación mide el binario de Chromium. La instalación de npm y las bibliotecas del sistema se ejecutaron fuera de esa medición. Los tiempos son muestras de este intento. Los ZIP descargados coincidieron con las huellas publicadas por GitHub. Los artefactos tienen una retención configurada de 14 días. [Artefacto Ubuntu](https://github.com/MauricioPerera/KDD/actions/runs/45625522872/artifacts/15026589273) · [Artefacto Windows](https://github.com/MauricioPerera/KDD/actions/runs/45625522872/artifacts/15027548962)

| Pasada | ID de e2e | SHA-256 de `report.json` |
| --- | --- | --- |
| Ubuntu, vacía | `01a212ed-952a-7af1-9829-43d0b0c9c315` | `e2f28f139aab62e515c98e2147077efc9de3873939df9b577aec00181bb8f4ff` |
| Ubuntu, con navegador | `01a212ed-a573-7190-b29f-4063bb9fc30c` | `5d4915fa8e597982b2bec78576c053c51f0f4371eba77ca81b431ae8a6515bda` |
| Windows, vacía | `01a212ed-c3f6-787c-84f1-29ff409063db` | `2b53c302072adc4653c2cd9302024961b9796c95b19c77d50058b3a5e99f744d` |
| Windows, con navegador | `01a212ed-e68f-79d3-a713-f0292cfc3ec3` | `9a900f31f11090ce03da6102dcf2db6606f7f2dd20ca9e32ac838682b77a9e69` |

### Contramuestras

- Retirar el v1 sintético produjo una aserción fallida en Chromium con código `1`. El caso sin evidencia siguió pasando.
- La selección vacía devolvió `2` con `NO_TESTS` y dejó intacto el reporte verde anterior. El verificador rechazó ese reporte al recibir el código real.
- El lanzador normal rechazó un destino con un reporte previo y un SHA existente que carecía del baseline del piloto. [Control de integración](https://github.com/MauricioPerera/KDD/blob/b23b941f209ec4297cecfb05e1e8073e0ff0001f/tools/kdd-board/browser-pilot/tests/pilot-live.test.mjs)

## CI habitual del mismo árbol

Pasaron dos suites de 2.736 casos en Ubuntu y dos en Windows con el runtime `39e402e4377aa5e97947888b9b5934202af8302e`. Los informes de cobertura corresponden a la primera pasada de cada sistema. Board pasó 107 de 107 por sistema. Los dos shards de post-init de Windows completaron sus asignaciones de 1.310 y 1.322 casos en una ventana común de 470 s sobre un límite de 600 s. Pasaron los builds de Pages del PR en ambos sistemas. [CI habitual e informes](https://github.com/MauricioPerera/KDD/actions/runs/45625522483)

## Autoría de pruebas con Goldfish

Se comprobó que una sesión MCP stdio nueva en el Board sintético abre el detalle de una tarea y que `test_lines` devuelve pasos reproducibles. El borrador incluyó el fragmento de autenticación sintético. Para adoptar pasos nuevos se acota el contexto al contrato y al fixture, se sanea el borrador, se revisan los selectores y se agregan las aserciones. La revisión humana fija esos archivos y sus dependencias en el baseline. La ejecución oficial usa las aserciones selladas. [Delegación efímera](../../knowledge/delegacion-efimera-goldfish.md) · [Receta del piloto](https://github.com/MauricioPerera/KDD/blob/b23b941f209ec4297cecfb05e1e8073e0ff0001f/tools/kdd-board/browser-pilot/README.md#proponer-pasos-con-goldfish)
