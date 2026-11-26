# Visor de evidencia de pruebas de KDD Board

## Qué se puede consultar

| Vista | Artefacto y procedencia | Detalle mostrado |
|---|---|---|
| **Consultar evidencia** en una tarea Git | Recibo de cierre en `docs/task-evidence/`, leído del commit consultado de `main`. | Ruta y huella SHA-256 del recibo, SHA consultado, SHA probado, SHA aprobado, ejecutor y total de casos. El recibo v1 aporta el total de la corrida. El v2 agrega casos ejecutados y omitidos por archivo del oráculo. Ambos muestran **Detalle por caso no registrado**. |
| **Evidencia Chromium** en el menú de Board | `receipt.json` y `report.json` de un paquete local del piloto. La vista es común al Board, con independencia del proyecto Git seleccionado. | SHA probado y aprobado, ID de la corrida y huellas SHA-256 del recibo y del reporte. Cada fila muestra el ID del caso, resultado, número de intento y duración en ms. El perfil exige listas vacías de adjuntos y muestra **Sin adjuntos** por caso. |

El lector Git contrasta el recibo con el nodo de tarea y el validador del cierre. Una tarea abierta figura como pendiente. El servidor distingue una tarea ausente de un recibo inválido. La vista resume el cierre sin exponer `stdout` ni `stderr`. El panel Chromium resume los casos sin mostrar pasos, logs, capturas ni descargas. [Contrato del visor](../../knowledge/contracts/board-test-evidence.md)

## Configurar el paquete Chromium

Antes de arrancar Board, configura `KDD_BOARD_BROWSER_EVIDENCE_DIR` con la ruta absoluta de la carpeta que contiene ambos JSON. Configura `KDD_BOARD_BROWSER_EVIDENCE_PIN` como `<SHA del checkout>:<SHA-256 de los bytes de receipt.json>`. El pin identifica el paquete elegido por el operador. Board verifica los hashes, la ascendencia del SHA aprobado respecto del checkout en el repositorio de Board y la concordancia del ID de corrida y los casos con el verificador del piloto. La consulta usa una copia temporal del reporte para verificar los mismos bytes. [Preparación y ejecución del piloto](https://github.com/MauricioPerera/KDD/blob/33eda53996b24bc5f12772e102c6ad91c863b4b8/tools/kdd-board/browser-pilot/README.md)

### Alias 8.3 de Windows

Un alias 8.3 es el nombre corto que Windows puede asignar al mismo directorio. El lector admite esa equivalencia en rutas locales de unidad. Recorre la ruta configurada con `lstat` desde la raíz y exige directorios ordinarios en cada componente. Si `realpath` expande el nombre corto, el recorrido canónico debe conservar la misma unidad y la identidad de cada directorio, comprobada con `dev` e `ino`.

Tras leer los dos JSON, Board repite la comprobación del recorrido y vuelve a cotejar el directorio final. Cada JSON debe ser un archivo regular con un solo enlace. Su identidad se comprueba antes de abrirlo, con el descriptor abierto y al terminar la lectura. Un enlace simbólico o una junction en cualquier componente, incluso debajo de un alias válido, o un archivo con un enlace duro adicional produce `409 BROWSER_EVIDENCE_INVALID` sin devolver casos. [Implementación del lector](https://github.com/MauricioPerera/KDD/blob/33eda53996b24bc5f12772e102c6ad91c863b4b8/tools/kdd-board/src/browser-evidence.ts)

## Verificación en `main` tras el PR #223

El 25 de noviembre de 2026, el [PR #223](https://github.com/MauricioPerera/KDD/pull/223) quedó integrado con sus seis commits en `33eda53996b24bc5f12772e102c6ad91c863b4b8`. Los tres workflows siguientes se comprobaron sobre ese SHA.

| Control | Ubuntu | Windows |
|---|---:|---:|
| Suite general | 2 pasadas de 2.736 casos | 2 pasadas de 2.736 casos |
| Cobertura de líneas en la primera pasada | 15.409 / 20.574 (74,90 %) | 15.843 / 20.574 (77,00 %) |
| Cobertura de ramas en la primera pasada | 5.717 / 8.324 (68,68 %) | 5.831 / 8.324 (70,05 %) |
| Pruebas de Board | 133 | 135 |
| Controles del visor en Chromium | 2/2 | 2/2 |

- **CI general.** Las cuatro pasadas registraron el mismo inventario de IDs. Los dos jobs de post-init de Windows ocuparon una ventana común de **450 s**, dentro de los 600 s. Las integraciones HTTP leyeron el recibo histórico v1 y un cierre v2 real, y rechazaron los enlaces. Windows leyó el mismo paquete por la ruta canónica y por un alias 8.3 real, y rechazó una junction bajo ese alias y un reporte con un segundo enlace duro. [CI de `main`](https://github.com/MauricioPerera/KDD/actions/runs/45695212205)
- **Chromium.** Los dos controles abrieron el recibo histórico en la vista de tarea y cotejaron las dos filas del paquete del piloto en su panel. En Windows el panel se abrió con un alias 8.3 real. El SHA del workflow identifica el código del visor bajo prueba. El panel mantiene el SHA propio del paquete que se consultó. [Workflow de Chromium](https://github.com/MauricioPerera/KDD/actions/runs/45695299037)
- **Pages.** El despliegue terminó correctamente. El índice público mostró los 2.736 casos y enlazó al CI de ese SHA. El [contrato publicado](https://mauricioperera.github.io/KDD/knowledge/contracts/board-test-evidence.md) coincidió byte a byte con el del commit. [Despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/45698930088)
