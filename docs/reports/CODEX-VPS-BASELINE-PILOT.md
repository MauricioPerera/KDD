# Piloto remoto de revisión de baseline con Codex VPS

El piloto sobre `a7e1c84` verificó la entrega del paquete por SHA-256, la
apertura de dos hilos nuevos, la validación del registro v1 y la repetición
de la solicitud con el mismo `runId`. Es un flujo optativo de
[revisión antes del baseline](../../knowledge/baseline-risk-review.md), fuera
del CI. La decisión de aprobar el SHA sigue el
[protocolo de calidad](../../knowledge/quality-approval.md).

## Flujo

1. **Preparar.** Ejecutar `python scripts/prepare_baseline_review.py prepare
   --base-ref BASE --candidate-ref CANDIDATO` con los SHA completos. Añadir
   `--source REVISION:RUTA` para las fuentes de apoyo y `--execution RECIBO.json`
   si hay resultados de ejecución. Guardar el paquete de evidencia, su
   `packet_sha256` y el `requestId` derivado. El hash cubre el JSON canónico del
   objeto `packet` dentro de la respuesta.
2. **Entregar.** Transferir esos bytes por un canal explícito y comprobar el
   SHA-256 en el destino. Entregar a cada revisor las fuentes que debe evaluar
   y el hash del paquete. Cotejar el mensaje encolado con el mensaje enviado
   cuando el proveedor ofrece ese registro. Que el modelo cite el hash
   acredita su declaración. La entrega se comprueba con los registros del
   entorno.
3. **Revisar en hilos nuevos.** Iniciar cada revisión sin un `conversationId`
   previo. Asociar los eventos de apertura con el turno, la conversación y el
   hilo. Conservar la respuesta original y el registro de apertura para el
   `handoff`. Cada revisor devuelve el SHA, el hash del paquete, sus lentes,
   las fuentes del `read_set` y los hallazgos. El registro de apertura acredita
   el primer turno. La lectura efectiva y la calidad del juicio siguen siendo
   materia de revisión.
4. **Validar.** Ejecutar `python scripts/prepare_baseline_review.py assemble
   --packet PAQUETE.json --handoff HANDOFF.json`. Conservar el `draft` v1 en
   JSON canónico y la `provenance` por separado. Comprobar el v1 con
   `python scripts/quality_baseline.py --base-ref BASE --candidate-ref CANDIDATO
   --review REVIEW-V1.json`. Si devuelve `review_ready: true`, el registro está
   listo para solicitar la aprobación humana.
5. **Repetir.** Reenviar la misma solicitud del diálogo con el mismo
   `requestId` y los mismos parámetros. Comparar el `runId`, la marca
   `duplicate` y los turnos registrados. Un cambio de evidencia produce otro
   hash y otra clave de solicitud.

El [contrato del adaptador](../../knowledge/contracts/vps-baseline-review.md)
define el formato de los artefactos, los estados de salida y las comprobaciones.

## Evidencia de a7e1c84

| Dato | Valor |
| --- | --- |
| Base | `00e1af78c298e0d8f960040cdb7727c5c091640f` |
| Candidato | `a7e1c849ea63631a3c9ec030d7ec122fd0472089` |
| Árbol del candidato | `34d947355e014e54f95318d132b1a6335889b38f` |
| Versión del adaptador usada | `f08cd8317f0c84173c8348b436fdfe6703b96989` |
| Paquete canónico verificado en el VPS | 40 992 bytes |
| SHA-256 del paquete | `99641659399a34f2656929fad6231b4e58bad6d3cf241607e571dca252e9d990` |
| SHA-256 del handoff | `8afc1dc340ded6014c4a646ae7f87b60437054e01dce7851a5ca3cb04c162ea2` |
| SHA-256 del v1 | `42121afad4b912d580661e6bf51939a5d5129bb4ffd6b8c5fc93e1385e84d8ca` |
| `requestId` | `59aa2570-ca47-5c55-a029-701bc26c80ec` |
| `runId` inicial y repetido | `run_f4621ad0-d11f-450f-ac99-5acf9c84dbc4` |

El VPS confirmó el hash al releer el archivo recibido por SSH en un directorio
temporal privado. Los mensajes de revisión se cotejaron por SHA-256 con su
contenido en SQLite. El revisor Git recibió los dos archivos nuevos completos.
El revisor del oráculo recibió el test completo y extractos de apoyo. Las
salidas se cotejaron con los recibos individuales de Codex VPS.

| Revisor | Primer turno | Hilo | Trabajos anteriores |
| --- | --- | --- | ---: |
| Git | `run_eeb1f88d-6be3-409a-98f2-846fbbc69f7b` | `01a20328-e4f7-73c1-bfde-959a0a5ba86a` | 0 |
| Oráculo | `run_966439de-1fb6-4f97-9b33-645523d18278` | `01a20326-a280-7892-9c8c-6cac987666f1` | 0 |

El servidor registró el inicio y la finalización de ambos turnos. Esos turnos
aportaron los dictámenes de las lentes `simplicity`, `implementation` y
`oracle`. El diálogo posterior se usó para coordinar el cierre. Al repetir
la solicitud, el VPS devolvió `duplicate: true` y el mismo `runId`. La consulta
de SQLite encontró una sola fila y la transcripción de dos turnos quedó
idéntica.

El adaptador y `quality_baseline.py --review` devolvieron código 0,
`review_ready: true`, dos fuentes Git comprobadas y cero hallazgos. En el
mismo SHA se ejecutaron los tres casos de
`tests.test_traceability_missing_blobs` dos veces en Windows y dos en una
copia aislada de Ubuntu en el VPS. Las cuatro ejecuciones dirigidas pasaron
fuera del CI. Los recibos originales se conservan en el registro local del
piloto.

## Incidencias del ensayo

El conector recortó el salto de línea final del primer envío. Un delimitador
después de los datos permitió cotejar los bytes de los mensajes posteriores.
Algunos primeros dictámenes llegaron con lentes adicionales o en prosa. Se
conservaron como evidencia y se abrieron hilos nuevos con el esquema v1
explícito al final de cada mensaje. Distintas revisiones Git bloquearon
por falta de evidencia en Ubuntu o por recibir solo un extracto del oráculo.
El resultado final se obtuvo con las ejecuciones de ambos sistemas y los
dos archivos completos para esa revisión.

[Flujo automatizado para nuevas revisiones](CODEX-VPS-BASELINE-AUTOMATION.md).
