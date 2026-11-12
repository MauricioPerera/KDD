# Batería adversarial del piloto ODD y EGM

Plan para la rama `codex/kdd-plugin-odd-egm-pilot` a partir del commit
`70673b589b8c64d111b165fb9f0c8fcae20c1d37`. Define 16 escenarios
adversariales y cuatro controles positivos. Las tablas fijan los resultados
esperados. La evidencia de ejecución se guarda en
`.agents/logs/plugin-odd-egm-pilot/adversarial/`.

El objetivo es detectar tres falsos verdes: un cambio de garantías que
entra por la ruta editorial, una revisión que se trata como aprobación y
una adopción que declara equivalentes dos pasadas con evidencia distinta,
incompleta o ajena. Las 17 integraciones del piloto son el punto de
partida. La batería amplía su cobertura y reutiliza las pruebas existentes
cuando ya aíslan la misma condición.
[Contrato de revisión](../../knowledge/contracts/plugin-odd-egm-review.md) ·
[Contrato de identidad de oráculos](../../knowledge/contracts/adoption-oracle-pass-identity.md).

## Preparación y señales

- Crear un repositorio consumidor temporal fuera de otro Git, con dos
  contratos inmediatos `A.md` y `B.md`, dos métodos por contrato, un
  README existente y un commit de adopción aprobado. Fijar un commit del
  validador con soporte de revisión y comprobantes. Crear un segundo pin
  distinguible para las pruebas de sustitución.
- Usar Git y Python 3.11 reales en Ubuntu y Windows. Reutilizar la
  [preparación de adopción](../../tests/adoption_remediation_support.py)
  y el [ejecutor del paso generado](../../tests/test_adoption_trusted_pr.py).
  Redirigir únicamente la descarga al Git local de pruebas. Inyectar una
  alteración por variante, sobre una copia del control positivo. Cuando
  importe el momento de la alteración, sincronizar con la salida de una
  pasada y registrar los eventos con centinelas temporales.
- Probar `review` con el lanzador instalado. Probar la adopción con
  `--approved-ref` tanto en terminal como con el paso generado de Actions.
  Para `review`, exit 0 indica inspección o registro listo, exit 1 indica
  revisión pendiente y exit 2 indica entrada rechazada. Para la adopción,
  exit 1 exige `KDD_PILOT.result=fail` si el workflow llegó al lanzador.
  Acreditar el motivo y la etapa del rechazo, además del código de salida.
  Cuando el archivo alterado sea el lanzador, invocar la copia aprobada desde fuera del checkout
  con `--repo-root`, tal como lo hace el paso generado.
- Guardar por caso el SHA de adopción, el SHA del validador, los SHA de
  base y candidato y el árbol cuando apliquen, el SO, la variante, el
  código de salida y el inventario observado. Comparar refs, índice,
  configuración y bytes del consumidor antes y después de cada revisión.
  En las variantes que alteran el checkout deliberadamente, comparar
  contra esa alteración controlada. Usar valores sintéticos para las
  entradas que imitan secretos.

## Casos adversariales

P0 cubre las garantías locales y los refuerzos propuestos para evitar
falsos verdes. P1 comprueba límites del flujo asistido o del despliegue.
Las expectativas de los refuerzos A12 y A13 se deben comprobar antes de
atribuirlas al piloto actual.

| ID | Prioridad | Alteración aislada | Resultado esperado |
| --- | --- | --- | --- |
| A01 | P0 | Sustituir la referencia de adopción por una vacía, `HEAD`, un SHA abreviado, un tag anotado o un commit existente de otra línea. | La revisión rechaza con exit 2. El PR rechaza con exit 1 antes de cargar el validador o ejecutar el centinela del candidato. |
| A02 | P0 | Cambiar el lock o un archivo administrado en HEAD, solo en el índice, o solo en el checkout con `assume-unchanged`. Probar además una ruta administrada enlazada fuera del repositorio. | La discrepancia bloquea aunque `git status` parezca limpio. El pin ajeno nunca aparece como verificado y el destino del enlace conserva sus bytes. |
| A03 | P0 | Inyectar por separado `GIT_DIR`, una ref de reemplazo, un Git señuelo en el checkout y un módulo Python señuelo vía `PYTHONPATH`. Inspeccionar un candidato con código y un diff externo con centinelas. | La inspección devuelve los OID y blobs originales cuando la entrada legítima es válida. Los centinelas quedan ausentes y el estado del consumidor permanece idéntico. |
| A04 | P0 | Hacer que el transporte entregue otro commit. En otras variantes, alterar un blob del tar, omitirlo, repetirlo o añadir un enlace o una ruta que salga del destino. | Falla la resolución o extracción. El revisor y los oráculos quedan sin ejecutar y el archivo centinela fuera del temporal conserva sus bytes. |
| A05 | P0 | Solicitar la ruta ligera para una errata mezclada con un cambio de oráculo, workflow o contrato. Probar además dos commits que cambian y restauran código, dejando un diff final de README. | La inspección devuelve `route=standard`, con motivo de alcance o historial según la variante, incluso con `--editorial-only`. |
| A06 | P1 | Cambiar solo un README o una guía para introducir una obligación nueva o instrucciones dirigidas al asistente. | El operador, o el asistente durante el ensayo supervisado, identifica el cambio semántico y omite la confirmación editorial. La prueba acredita la decisión del flujo asistido. El clasificador de rutas por sí solo depende de esa confirmación. |
| A07 | P0 | Reutilizar un registro válido con un commit diferente que comparte el mismo árbol. En otras variantes, adulterar únicamente el árbol declarado o repetir una clave del JSON. | Exit 2 y diagnóstico `REVIEW_IDENTITY` para el commit o árbol. La clave duplicada provoca `REVIEW_SCHEMA`. El lanzador no emite un veredicto JSON. |
| A08 | P0 | En un cambio de riesgo alto, rebajar el riesgo declarado, usar al autor como segundo lector, dejar un lector en `not_run`, omitir una perspectiva o fuente modificada, o cerrar un `major` sin decisión válida. | Cada registro válido pero insuficiente devuelve exit 1, `review_ready=false` y el hallazgo específico. Una repetición de identidad que invalida el esquema se rechaza con exit 2. |
| A09 | P0 | Generar un `review_ready=true` legítimo y lanzar después el paso de PR con la referencia de adopción ausente. Repetir con una revisión que afirma traer una aprobación en un campo extra. | El PR sigue bloqueado sin su referencia externa. El campo extra causa un error de esquema. La revisión no escribe refs, índice, configuración ni archivos aprobados. |
| A10 | P0 | Sustituir un solo comprobante por JSON truncado, una clave duplicada, versión booleana, un contrato ausente o repetido, una ruta no canónica o IDs vacíos o duplicados dentro de un contrato. | Exit 1 en `stage=oracle`. Cada variante se rechaza por el defecto concreto y el resultado fallido carece de `oracle_inventory` aprobado. |
| A11 | P0 | Dejar el segundo comprobante ausente tras una primera pasada válida. Probar también un archivo ya presente en el destino o un comprobante señuelo en el checkout. | La primera evidencia nunca acredita la segunda pasada. El gate rechaza la colisión y preserva los bytes existentes. El señuelo del checkout queda sin usar. |
| A12 | P0 | Alternar dos métodos reales de un mismo contrato mediante `load_tests`. En una variante, ambos devuelven el mismo `id()` personalizado aunque los centinelas distinguen los métodos. Reusar el caso existente de intercambio de IDs entre A y B. | El criterio de aceptación exige rechazar los métodos distintos aunque ambos conteos y el ID visible coincidan. Si la variante con `id()` personalizado sale verde, registrar el falso verde como hallazgo y conservar ambos centinelas. |
| A13 | P0 | Alterar de forma persistente un helper protegido al terminar la primera pasada. En variantes separadas, añadir un contrato inmediato válido o cambiar el lock después de que la segunda pasada haya producido su comprobante. | El helper alterado bloquea antes de iniciar la segunda pasada. El refuerzo propuesto exige detectar el contrato extra y el lock cambiado antes de emitir `result=pass`, incluso con comprobantes válidos. Un verde en esas variantes se registra como hallazgo. |
| A14 | P0 | Imprimir un PASS o un inventario plausible y terminar sin casos. Probar por separado un skip, un fallo y un timeout después de iniciar un caso. | La adopción bloquea cada variante. El stdout fabricado y un comprobante parcial carecen de valor aprobatorio. El diagnóstico distingue fallo, omisión y timeout. |
| A15 | P1 | En un entorno desechable, medir hasta dónde puede falsificar evidencia un oráculo Python deliberadamente hostil que ya fue incluido en el baseline confiable. | Documentar el resultado como límite del modelo. Esta prueba explora el aislamiento y no acredita resistencia a un host, runner u oráculo aprobado hostil. |
| A16 | P1 | En un consumidor desechable, hacer que el candidato publique un check verde con el nombre del check esperado sin ejecutar el paso aprobado. | Verificar qué workflow y árbol acredita la regla real. Si solo se exige el nombre, registrar la brecha. Una simulación local acredita el cuerpo del paso, y la protección alojada se comprueba en el servicio. |

El resultado de A12 verifica la identidad del método ejecutado. A15
explora código que modifica deliberadamente su instrumento. El modelo de
confianza del piloto presupone un host, runner y oráculos aprobados
confiables. Un JSON EGM estructuralmente válido tampoco autentica a una
persona. [Ejecución de oráculos](../../knowledge/contracts/oracle-execution.md) ·
[Adopción confiable en PR](../../knowledge/contracts/adoption-trusted-pr.md) ·
[Protocolo de revisión](../../knowledge/baseline-risk-review.md).

A12 parte de que el recorder obtiene la etiqueta mediante `test.id()`.
A13 parte de que el lanzador conserva la lista inicial de contratos y
la vuelve a comprobar tras cada pasada. El ensayo añade una ruta al
directorio al final, cuando el gate ya generó su comprobante. Son
hipótesis derivadas del código, pendientes de reproducción.
[Recorder](../../scripts/unittest_oracle_runner.py#L38) ·
[Lanzador](../../tools/kdd-adoption/validate.py#L405).

## Controles positivos y orden

| ID | Control | Resultado esperado |
| --- | --- | --- |
| C01 | Editar una errata de README en un commit y confirmar tras leer el diff. | Exit 0, `route=lightweight`, commit exacto y cero efectos secundarios. |
| C02 | Presentar un cambio de riesgo alto con dos lectores independientes, las tres perspectivas y todas las fuentes. | Exit 0, `review_ready=true`, árbol exacto y aprobación humana todavía pendiente. |
| C03 | Ejecutar los mismos casos de A y B en orden inverso. Compartir un ID entre contratos. | Terminal y paso generado pasan con el mismo pin e inventario canónico. Cada contrato conserva su entrada independiente. |
| C04 | Usar la ruta histórica sin referencia de adopción y con un pin anterior. | Conserva una pasada y el contrato de salida histórico. El modo aprobado con ese pin rechaza la falta de comprobantes. |

1. Ejecutar C01–C04 y atacar primero A12, A13, A10 y A11. Cubren falsos
   verdes con evidencias aparentemente correctas.
2. Completar A01–A05, A07–A09 y A14 por el punto de entrada indicado.
   Donde ya haya cobertura unitaria, reutilizar los fixtures y verificar
   que el lanzador preserve el veredicto y los efectos observables.
3. Comprobar la fuerza de la batería con cinco mutantes aislados. Comparar
   solo conteos o solo el conjunto global debe romper A12. Reutilizar el
   primer comprobante debe romper A11. Omitir la comprobación final del
   checkout debe romper A13. Aceptar una revisión ajena debe romper A07.
   Cada mutante debe fallar por la garantía alterada. Un fallo de
   preparación deja la variante inconclusa.
4. Para aceptar el refuerzo local, exigir todos los P0 y los cuatro
   controles verdes en ambos SO, más las dos pasadas completas del
   mismo SHA con los 2.344 IDs existentes y los nuevos. Conservar los
   SKIP de aplicabilidad existentes y exigir ejecución de cada prueba
   nueva. Registrar A06 y A15 como ensayos de alcance y A16 como evidencia
   de despliegue cuando se pruebe el workflow alojado.

Cualquier falso verde P0 bloquea la aceptación del refuerzo. El registro
de resultados debe identificar qué se ejecutó y qué quedó inconcluso.
[Aceptación por obligación](../../knowledge/acceptance.md).
