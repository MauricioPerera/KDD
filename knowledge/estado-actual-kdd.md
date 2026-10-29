---
type: 'Concept'
title: 'Estado verificable de KDD y evidencia historica'
description: 'Estado verificado de main, historial de pruebas y limites de KDD.'
tags: ['kdd', 'reference', 'verification', 'tasks', 'bootstrap', 'ci', 'pages']
---

# Estado verificable de KDD

**KDD organiza el desarrollo mediante conocimiento enlazado, contratos y
oráculos aprobados, implementación delimitada y evidencia asociada a commits.**
Actualmente dispone de una plantilla inicializable, validadores, una CLI de
tareas y KDD-Board integrados con Git. El flujo se ha comprobado desde un
proyecto vacío hasta su calidad de producto en CI.

## Actualizacion verificada del 28 de octubre de 2026

El main `92a594e3701b25809925c8d6e1842fa0b6b0c76f` integra el PR140 con sus
[dos commits originales](https://github.com/MauricioPerera/KDD/pull/140).
El [CI de main](https://github.com/MauricioPerera/KDD/actions/runs/40791293282)
paso en Ubuntu y Windows, con dos pasadas de 1651 IDs por sistema. Hubo
10 skips declarados en Ubuntu y 9 en Windows; el inventario incluye esos IDs.
El [despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/40795357919)
reconcilio los cuatro reportes y publico el contador de ese run.

La agrupacion de lecturas Git del PR140 redujo de 60 a 59 procesos Git en un
fixture instrumentado con resultados identicos. Las dos muestras remotas son
insuficientes para atribuirle una reduccion del tiempo total. En el CI de
main citado, el job Windows tardo 36:44 y Ubuntu 7:35; el
[diagnostico historico de CI](ci-diagnostico-2026-10.md) aporta contexto sin
prometer que las mediciones sean comparables causalmente.

La auditoria posterior identifico mejoras de arranque de Board sin Git, de
seleccion de raiz Git y de aislamiento de fixtures. La propuesta de esta
rama implementa las correcciones; aun no forman parte del main citado ni
cuentan con CI remoto. Su [integracion Board](board-git.md) describe el flujo.
La aprobacion del baseline no sustituye la revision de producto ni autentica
por si sola una decision humana. Los cinco checks de proteccion de main se
mantienen; la fusion de PR140 tuvo la excepcion puntual a Entire autorizada.

## Corte historico del 24 de octubre

Este corte, fechado el **24 de octubre de 2026, America/Mexico_City**, distingue
la revision publicada de la propuesta local. Las reglas normativas siguen en
los nodos enlazados; los conteos corresponden a las revisiones indicadas.

| Revision observada | Estado y evidencia |
| --- | --- |
| `main` en ese corte: [`db1717fa`](https://github.com/MauricioPerera/KDD/commit/db1717fa3e6d3497498afbd79a45b07718b1d3ce), PR127 | [CI satisfactorio](https://github.com/MauricioPerera/KDD/actions/runs/40141077949), Ubuntu/Windows, dos pasadas de 1182 casos por SO; [Pages desplegado](https://github.com/MauricioPerera/KDD/actions/runs/40142198858). |
| Rama local en ese corte `codex/pages-ci-inventory`: `34bdfb708ca044f1e2532f733863337a4d894799` | Baseline aprobado e implementacion comprobada localmente: 19 gates, 86 contratos, 143 nodos, dos pasadas de 1207 casos y 40 pruebas de Board por SO. Conserva los 1182 IDs anteriores y agrega 25 sin nuevas omisiones. |
| Publicacion del contador nuevo en ese corte | Pendiente de publicar la rama, verificar CI en GitHub y desplegar Pages. Los 1207 casos son evidencia local; no representan aun el sitio publico. |

Las cuatro pasadas locales coinciden en el digest de IDs
`5f302ea4517a7329e70dd8f6889c9d15540200b8fcb5fb083c40e7a28eb2ac8e`.
Las omisiones previas se conservan: 9 en Windows y 10 en Ubuntu por pasada.
El publisher real paso en modo preview y con los cuatro reportes locales.
El contexto de transporte de esa integracion usa un run sintetico;
no constituye una ejecucion autenticada de GitHub Actions.

## Componentes y responsabilidades

| Componente | Responsabilidad implementada | Referencia canónica |
| --- | --- | --- |
| Conocimiento OKF | Conservar contexto, decisiones y modelos en nodos Markdown enlazados. | [Especificación OKF](OKF-SPEC.md) |
| Task Contract y oráculo | Definir qué se implementa y cómo se comprueba; conservar la integridad de las pruebas mediante sello y referencia aprobada. | [Validación](validacion.md), [supervisión humana](supervision-humana.md) |
| Task y diario Git | Registrar el avance operativo en nodos de `main`, con una rama de implementación por tarea e historial de transiciones validable. | [Modelo Task](data_models/git-task.md), [tareas con Git](git-tasks.md) |
| CLI y KDD-Board | Operar el mismo coordinador; leer tareas confirmadas de `main` y devolver el commit real de cada cambio de estado. | [CLI](contracts/task-cli.md), [integración del tablero](board-git.md) |
| Bootstrap | Adaptar la plantilla a la identidad del proyecto, retirar ejemplos e historial operativo heredado y preparar el CI de producto. | [Inicializador](contracts/init-project.md), [arranque guiado](contracts/bootstrap-project.md) |
| Política de calidad | Delimitar archivos protegidos y cambios permitidos; ejecutar checks estructurales, funcionales, adversariales y de interfaz según el producto. | [Aprobación de calidad](quality-approval.md) |
| CI | Ejecutar validación y tablero en Ubuntu/Windows, con runtime revisado fuera del checkout, dos pasadas completas y reportes por ID; exigir calidad de producto en proyectos inicializados. | [Calidad desde el arranque](bootstrap-product-quality-ci.md), [tiempo del CI](ci-runtime.md), [frontera de confianza](ci-audit-remediation.md) |
| Pages | Compilar el sitio real en PR de ambas plataformas y reconstruir al desplegar el SHA de main cuyo CI paso. La rama local agrega cotejo de inventarios de las cuatro pasadas y discovery estricto. | [Build en PR](pages-pr-validation.md), [inventario](pages-ci-inventory.md), [operacion](../site/README.md) |

El **ciclo del contrato** (`draft → validated → implemented → verified`) y el
**estado de la tarea** son dimensiones distintas. Una tarea lista para comenzar
necesita una referencia explícita del contrato aprobado; el cierre necesita
evidencia de ejecución sobre la implementación integrada. Las responsabilidades
de definición, ejecución y revisión se desarrollan en la
[metodología de ejecución](metodologia-ejecucion.md).

## Flujo operativo consolidado

1. **Preparar el proyecto.** Inicializar con su `OWNER/REPO`, definir conocimiento,
   contratos, oráculos y `quality/product.json` propios. El proyecto comienza
   sin las tareas de ejemplo TASK-001/TASK-002 ni sus evidencias heredadas.
2. **Revisar las referencias.** La persona revisora aprueba commits completos.
   `KDD_APPROVED_BASELINE_REF` controla contratos/oráculos y
   `KDD_QUALITY_APPROVED_REF` controla la política y sus archivos protegidos.
   Pueden coincidir; el bootstrap no selecciona ni aprueba esas referencias.
3. **Registrar y ejecutar la tarea.** CLI o tablero recorren
   `backlog → ready → in_progress → done`; el bloqueo admite
   `in_progress → needs_human_input → ready`. Cada transición crea un commit.
   La implementación se realiza en `task/TASK-NNN`.
4. **Integrar y cerrar.** El coordinador o la persona responsable integra la
   rama preservando sus commits. `finish` prueba el `main` limpio con el
   oráculo aprobado y crea después el commit de cierre con evidencia durable.
   El tablero no realiza el merge ni el push.
5. **Publicar y verificar.** El flujo autorizado del repositorio publica el
   historial. El CI comprueba el checkout actual con un runner de calidad
   extraído del commit aprobado a un temporal externo; valida integridad y
   perímetro y ejecuta los checks dos veces.

El procedimiento y sus precondiciones completas viven en
[tareas con Git](git-tasks.md) y [calidad desde el arranque](bootstrap-product-quality-ci.md).
En el workflow generado, una política ausente o una referencia inválida produce
**FAIL**. El **PASS de calidad** requiere la ejecución satisfactoria del paso;
la ausencia de configuración no se acepta como SKIP satisfactorio.
El repositorio plantilla conserva su configuración opcional de ejemplos;
la obligatoriedad de `quality/product.json` corresponde a los proyectos inicializados.

## Evidencia historica de un proyecto nuevo

La demostración pública
[kdd-bootstrap-e2e-20261023](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023)
se creó exportando KDD
[`7886578b`](https://github.com/MauricioPerera/KDD/commit/7886578b8e4ce9f107851a4d7873ac9ab880dec8),
que incorpora el PR120, sin copiar su historial Git.
Se inicializó con identidad propia, se abrió KDD-Board vacío y se implementó
un normalizador de títulos con CLI. El stub fue rechazado antes de implementar.
Los siete cambios de estado se realizaron desde el tablero.

| Operación de TASK-001 | Commit original conservado |
| --- | --- |
| Crear: `backlog` | [`2157f49b`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/2157f49b0b0fb14609ddd8330ae3ea99e71273a9) |
| Aprobar: `ready` | [`4a62c465`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/4a62c465b6c605d810baf48ab3a1e7d4c4907793) |
| Iniciar: `in_progress` | [`800b8f03`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/800b8f036402413853e130174608bfc2c8235baa) |
| Bloquear: `needs_human_input` | [`cbd011e8`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/cbd011e83cda6b3448c230b9e663498a78cb259e) |
| Reanudar: `ready` | [`0e4198f8`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/0e4198f8ac00c446dc4b64795c1679b64f58771c) |
| Reiniciar: `in_progress` | [`dde4a4c4`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/dde4a4c41d664d74e6863335efe231c34b2bad18) |
| Implementar en la rama de tarea | [`c9a24bb2`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/c9a24bb2c25ea908665e0923804ea18bb36c8e1c) |
| Integrar conservando la implementación | [`ec672b8f`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/ec672b8f5793c854108b359fdc7330351532355f) |
| Cerrar: `done` | [`27f560ea`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/27f560ea18710c2b3017ccd8b743e328427328fd) |

El cierre conserva **21 pruebas** y la referencia histórica aprobada
`36efe59798f15579bca495da40f864302c890cb2`. Su
[evidencia versionada](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/blob/27f560ea18710c2b3017ccd8b743e328427328fd/docs/task-evidence/TASK-001-ec672b8f5793c854108b359fdc7330351532355f.json)
identifica el merge probado `ec672b8f`, el oráculo, el target y el resultado.
Un intento previo de cerrar sin implementación integrada fue rechazado sin
crear un commit de cierre.

El [primer CI](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/actions/runs/40056782873)
detectó un error real del oráculo en Windows: decodificaba salida UTF-8 con el
locale CP1252. Se añadió una regresión que fallaba antes del arreglo y se hizo
explícita la decodificación, conservando las aserciones anteriores. La persona
revisora aprobó después
[`4636c9e9`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/4636c9e9ff7ec62069760d5c9b2af7838de706ae)
para ambas variables de CI. Ese cambio pertenece a la demo; el bootstrap de
KDD de esa demostracion corresponde a `7886578b`, no al main de este corte.

| Verificación final de la demo | Resultado observado |
| --- | --- |
| CI de `4636c9e9` | [Run 40058077407](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/actions/runs/40058077407): cuatro jobs en `success`. |
| Calidad de producto por SO | `quality/product.json`: **PASS**, 9 pruebas funcionales + 8 adversariales + 5 de CLI, dos rondas, sin omisiones de producto. |
| Suite general por SO | 993 casos enumerados en cada una de dos pasadas; 47 omisiones en Ubuntu y 46 en Windows. |
| Política y workflow | 68 rutas protegidas existentes; workflow generado conservado sin edición manual. |
| Historial | Los nueve commits de la tarea permanecen como ancestros; la evidencia histórica de 21 pruebas sigue intacta. |

Las **22 pruebas actuales** corresponden al oráculo corregido del CI; el cierre
histórico mantiene sus **21 pruebas** originales. El PASS de producto no elimina
los SKIP de otras capas opcionales, como seguridad sin hallazgos aportados.
La revisión fuente historica de KDD también tiene
[CI satisfactorio](https://github.com/MauricioPerera/KDD/actions/runs/40052262735)
con los cuatro jobs Ubuntu/Windows y 66 contratos. El conjunto de Nivel 1
mantiene 19 gates; los controles del diario de tareas son adicionales. El
preflight local incluye un control de atestación más y muestra 20 comprobaciones.

## Varias tareas y dependencias comprobadas

La demostracion publica
[kdd-dependencies-e2e-20261023](https://github.com/MauricioPerera/kdd-dependencies-e2e-20261023)
ejecuto cuatro tareas con grafo A -> B/C -> D desde KDD-Board. Verifico
rechazos por dependencias pendientes, bloqueo/reanudacion, ramas y cierres
con evidencia, conservando los 28 commits originales y cuatro ramas remotas.
Su [CI de cierre](https://github.com/MauricioPerera/kdd-dependencies-e2e-20261023/actions/runs/40067038669),
en `9101714f03c637b1ae821433461e58b64e93b917`, paso los cuatro jobs:
1025 casos dos veces por SO y 54 pruebas de producto en dos rondas, sin SKIP
de producto. Es evidencia historica de ese proyecto, no el inventario actual
de KDD. El [piloto reproducible](contracts/dependency-workflow-e2e.md) agrega
integracion HTTP real al bootstrap y al flujo de dependencias.

## Mejoras integradas y rendimiento medido

La [deduplicacion](contracts/ci-execution-deduplication.md) agrupa comandos
exactamente iguales dentro de una invocacion, evita el doble disparo push de
rama/PR y cancela runs nativos superados del mismo PR. El
[paralelismo acotado](ci-runtime.md), integrado mediante PR123, mantiene
cuatro jobs, Ubuntu/Windows y dos pasadas completas consecutivas. El perfil
nativo usa cuatro workers para contratos y suite Ubuntu, y seis para la suite
Windows; los consumidores conservan uno por defecto. Ver el
[perfil por sistema](ci-windows-suite-concurrency.md).
No se reutiliza evidencia entre commits, SO, pasadas ni invocaciones.

La comparacion del PR123 uso dos muestras anteriores con arboles iguales
([run 40073508632](https://github.com/MauricioPerera/KDD/actions/runs/40073508632),
[run 40094563794](https://github.com/MauricioPerera/KDD/actions/runs/40094563794))
y dos intentos satisfactorios del mismo head `5d73c163`
([run 40112023129](https://github.com/MauricioPerera/KDD/actions/runs/40112023129)).

| Mediana de dos muestras, sin cola ni Pages | Antes | Despues | Reduccion observada |
| --- | ---: | ---: | ---: |
| Primer job iniciado a ultimo terminado | 33 min 53 s | 14 min 45 s | 56,47 % |
| Suma de los cuatro jobs | 39 min 6,5 s | 18 min 11,5 s | 53,48 % |

Los 1102 IDs anteriores se conservaron y se agregaron 27, con 1129 casos
por pasada y las mismas omisiones previas. Estas medianas describen esas
muestras; las correcciones de seguridad, fixtures y Pages posteriores
quedan fuera de la comparacion. No son una promesa de duracion del main actual.

Los [siete pendientes del piloto](pending-improvements.md) se integraron en
PR122: dependencias de Board, procedencia de scans, evidencia de tareas
permitida por politica, errores WebMCP, lecturas Git por lote, Actions con
Node24 y piloto reproducible. PR124 agrego el runtime confiable, cancelacion
de arboles y contabilizacion de fixtures/hooks. PR125 corrigio el import como
paquete; PR126 agrego el build real de PR y PR127 ajusto los fixtures de
arranque. Los protocolos enlazados conservan el alcance de cada cambio.

## Correccion del contador de Pages en el corte historico

En el despliegue de `db1717fa` se observaron 1145 casos frente a los 1182 del
CI: faltaban parsers de discovery y un import fallido se contaba como un solo
`_FailedTest`. El [arreglo local](pages-ci-inventory.md) rechaza discovery
incompleto y compara IDs de las cuatro pasadas del run/intento/SHA exactos
antes de crear el bundle. El control negativo real reprodujo el defecto del
builder anterior y verifico el rechazo del nuevo en Windows/Ubuntu.
En ese corte faltaba confirmar el transporte de artifacts y el resultado publico.
La actualizacion superior enlaza al despliegue ya verificado en main.

## Alcance de las garantías y trabajo pendiente

- **Integridad y adecuación.** El sello y la referencia detectan alteraciones;
  la fuerza del oráculo y la corrección de los requisitos requieren revisión.
  El cierre certifica el SHA probado con su oráculo, no revisiones futuras.
- **Confianza.** Git, el runner y las variables de aprobación necesitan control
  externo. Un SHA explícito no autentica por sí solo la decisión humana. Las
  protecciones de GitHub se configuran en cada repositorio nuevo.
- **Operación local.** Board usa localhost y token; el coordinador tiene lock
  local. La coordinación distribuida y el acceso multiusuario siguen pendientes.
- **Nivel 2 y dominios opcionales.** Los perfiles nativo/MCP y las capas de
  seguridad, privacidad, accesibilidad y otros dominios tienen mecanismos propios.
  Esta demo no constituye una validación integral de esas capacidades.
- **Arranque remoto.** Variables, protecciones y disponibilidad de Actions son
  configuración externa. La demo requirió habilitar Actions desde GitHub; el
  bootstrap no automatiza esa administración.
- **Publicacion de la mejora local en ese corte.** Publicar y revisar la rama del contador,
  verificar CI en GitHub y comprobar despues el despliegue y la cifra publicada.
  Los cambios de workflows siguen sujetos a la revision de confianza; este
  documento no autoriza modificar protecciones.
- **Proxima validacion de uso.** Ya hay pilotos CLI de una y cuatro tareas con
  dependencias. Falta medir colaboracion concurrente real, requisitos de interfaz
  y coste de revision en un producto mayor. El piloto HTTP automatizado no
  equivale a comprobar un navegador renderizado ni un equipo distribuido.

Los límites técnicos completos se mantienen en
[garantías verificables](verification-guarantees.md). Las ampliaciones de
alcance necesitaran contratos y evidencia propios; la publicacion del
contador conserva los contratos y el baseline ya aprobados.
