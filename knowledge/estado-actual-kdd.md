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

## Estado integrado al 6 de noviembre de 2026, 23:38 UTC

La revision verificada de `main` es
[`0ac8666d9dc686e749890ca73bf3a736878c377a`](https://github.com/MauricioPerera/KDD/commit/0ac8666d9dc686e749890ca73bf3a736878c377a).
Integra [PR161](https://github.com/MauricioPerera/KDD/pull/161) con sus 41
commits originales y [PR164](https://github.com/MauricioPerera/KDD/pull/164)
con su unico commit `0fb9e41ec7f538bf096a45b9562007d821061cdb`, que tambien
es el baseline aprobado del oraculo. Los cortes inferiores conservan el
estado que tenian las ramas al registrarlos.

El [CI de main, intento 1](https://github.com/MauricioPerera/KDD/actions/runs/42308617660)
paso los cuatro jobs. El [build y despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/42313182858)
paso para el mismo SHA; la web publica respondio HTTP 200, mostro 2118 IDs
y 19 gates y enlazo ese run exacto. El
[informe versionado](../docs/reports/KDD-STATE-2026-11-06-REPORT.md)
conserva las referencias, tiempos y limites de esta observacion.

| Evidencia remota de main | Ubuntu | Windows |
| --- | ---: | ---: |
| Pasadas completas de la plantilla | 2 | 2 |
| IDs exactos por pasada | 2118 | 2118 |
| SKIP de aplicabilidad por pasada | 10 | 9 |
| Job validate | 8 min 51 s | 39 min 12 s |
| init-project real | 153,37 s | 515,16 s |
| Casos / modulos post-init | 2014 / 182 | 2014 / 182 |
| SDK MCP genuino | 8/8, cero SKIP | 8/8, cero SKIP |
| Board | 86/86 | 86/86 |

Los cuatro inventarios coinciden literalmente. El post-init conserva su
inventario propio y 102 SKIP en Ubuntu /101 en Windows. Las cinco
integraciones nuevas de identidad se ejecutan sin SKIP. Estos conteos
incluyen omisiones declaradas y no miden porcentaje de cobertura de codigo.

### Capacidades integradas

La plantilla ya conecta conocimiento OKF, contratos atomicos y de grupo,
oraculos revisados, tareas y dependencias, CLI/Board, bootstrap y calidad de
producto obligatoria. La tabla de componentes inferior enlaza sus fuentes
normativas y los pilotos de proyectos nuevos conservan su evidencia historica.
La compatibilidad de contexto v0.3 y los controles de aceptacion estan
disponibles con los limites de cada perfil.

PR161 integra las correcciones de bootstrap, historial Git, fixtures,
lecturas agrupadas, reducciones de complejidad y temporales Windows descritas
en su alcance. Su publicacion, fusion y verificacion posterior ya terminaron.
PR164 agrega el [observador de identidad estable](process-observer-identity.md):
retiene el objeto del proceso antes de confirmar readiness y consulta ese
objeto al retornar calidad. Los controles reales conservan vecinos, deteccion
de fugas, escrituras tardias y liberacion de recursos. El incidente historico
del PID 3224 conserva una causa inconclusa; la regresion nueva verifica el
mecanismo corregido.

El runtime revisado sigue siendo `74d357f7099651b9b39dc8088f725183a672ec94`.
Los perfiles conservan Ubuntu/Windows, ambas pasadas, los timeouts, el
presupuesto Git seguro de 62 procesos y los 19 gates. La fusion de PR164 uso
la excepcion humana puntual a Entire autorizada por el usuario; los cinco
checks requeridos pasaron y las protecciones, strict y las 57 entradas del
registro externo permanecieron intactos. El main local quedo limpio y
sincronizado en el SHA citado al terminar la comprobacion.

### Pendientes vigentes

1. **Rendimiento Windows.** El objetivo exige init <480 s en tres workflows
   completos consecutivos del mismo head, con ambos sistemas y ambas pasadas
   correctos. La muestra actual de main mide 515,16 s y no cumple ese criterio,
   aunque pasa el timeout de 600 s. El PR midio 339,12 s y su job Windows
   27 min 37 s; son SHA y eventos distintos y no forman una comparacion causal
   ni tres muestras aceptadas. Seguir el [protocolo vigente](windows-ci-test-temp.md).
2. **Repetibilidad del observador.** PR y main pasan con las cinco regresiones
   reales. Seguir conservando los resultados concurrentes y cualquier fallo
   nuevo; esas observaciones no demuestran ausencia universal de intermitencia
   ni explican retrospectivamente el PID del incidente anterior.
3. **Deuda y adopcion a mayor escala.** Hace falta otra medicion global de
   complejidad para priorizar el siguiente modulo. La colaboracion distribuida,
   el uso multiusuario y la evaluacion de un producto mayor siguen fuera de
   los pilotos actuales. Los limites de firmas y fuentes dinamicas del perfil
   v0.3 permanecen documentados abajo; su ampliacion necesita alcance propio.

Este corte registra una entrega funcional integrada y su evidencia. La
aceptacion de rendimiento continua abierta. Los resultados de CI enlazados
corresponden al codigo citado; no certifican cambios documentales posteriores.

## Corte historico del 6 de noviembre de 2026, anterior a la publicacion de temporales

Este corte, preparado antes de publicar la nueva ubicacion temporal, distingue
`main`, lo publicado en un PR y el candidato local. Los resultados posteriores
se registran en el PR sin reinterpretar la evidencia de este corte.
La funcionalidad verificada y la aceptacion de rendimiento son resultados
separados. Los conteos son inventarios de casos, incluidos sus SKIP; no son
porcentajes de cobertura de codigo.

| Revision | Estado comprobado |
| --- | --- |
| `main` `c094317407cbb51448dc6282e531ed76be318bff` | Integra PR163 y la seleccion de Git nativo con layouts ucrt64/mingw64. El [CI de main](https://github.com/MauricioPerera/KDD/actions/runs/41519134701) paso contratos, SDK, ambas pasadas y Board en Ubuntu/Windows. [Pages](https://github.com/MauricioPerera/KDD/actions/runs/41525501404) se desplego para ese SHA. |
| [PR161](https://github.com/MauricioPerera/KDD/pull/161), head `b9778924e7282a293721cb10b3623460e0bacb1f` | Abierto, con 38 commits conservados; aun no integrado en main. Su [CI](https://github.com/MauricioPerera/KDD/actions/runs/42155573090) paso los cuatro jobs funcionales y las dos suites de 2110 IDs por OS. Init Windows tardo 568.9987731 s: FAIL del objetivo de rendimiento. |
| Codigo local `fe73f58a83fba7592fd76f87d36ac50e4d8534f7` y esta formalizacion | Agrega temporales privados bajo RUNNER_TEMP solo al CI nativo Windows. Baseline `d221236bdcfdc3d82e353fd7cf644c97c2a0c7c4` y diff del workflow aprobados antes de implementar. Todavia no publicados al preparar este corte. |

La base ya permite modelar conocimiento y contratos, aprobar oraculos,
inicializar proyectos, operar tareas desde CLI/Board con estados versionados
en Git y verificar calidad de producto en CI. Los pilotos historicos y los
limites de esas garantias se conservan abajo. Las correcciones del PR161
siguen siendo trabajo de rama; no se presentan como capacidades integradas
en el `main` de este corte.

En el candidato local se conservan los 190 archivos Python de pruebas previos
y los 2110 IDs; las tres integraciones nuevas elevan el inventario a 2113.
Las nuevas pruebas comprueban herencia Python/Node/Git, aislamiento, aliases
y errores reales de escritura, tambien en copias inicializadas sin .git.
Pasan las contramuestras y actionlint en ambos sistemas.

El perfil local corregido pasa 185 comandos de contratos por OS. Init completo:
Windows 408.2287113 s /Ubuntu 177.3177953 s; post-init con 2009 casos y los
101/102 SKIP anteriores. Ubuntu completo ambas suites de 2113 IDs con sus
10 SKIP exactos. Windows completo dos pasadas nuevas de 2113 IDs con sus
9 SKIP anteriores y los mismos motivos, en 383.823/432.663 s. Su controlador
anterior habia quedado inactivo; el reporte parcial se conserva y no cuenta
como PASS. Se reconcilian los 21 pasos previos completados y las dos suites
nuevas del mismo codigo, sin presentar el controlador parcial como completo.
SDK ejecuto sus ocho casos genuinos sin SKIP y Board paso 86/86 por OS.
Un intento local anterior omitia la variable del SDK y agregaba tres SKIP;
se conserva, pero se excluye de la prueba de cobertura conservada.

### Lo aprendido del CI

- Un CI funcional verde puede incumplir el plazo de rendimiento: 569 s no
  satisface el objetivo de 480 s, aunque quede por debajo del timeout de 600 s.
- Reducir procesos Git o acelerar un modulo no demuestra ahorro del comando
  completo. La ultima lectura agrupada mejoro su modulo local, pero el init
  remoto paso de 567.65 a 569.00 s; el objetivo sigue abierto.
- El post-init es trabajo completo de una copia inicializada. Su inventario
  y sus SKIP deben comprobarse aparte de las dos suites de la plantilla.
- La ocupacion agregada del ultimo post-init fue 4429.08 s: /8=553.64 s,
  frente a 559.75 s de pared. Queda poco margen de cola; reordenar por si solo
  no acredita 480 s. Esa suma no mide tiempo de CPU.
- Los fixtures remotos usan C: y RUNNER_TEMP usa D:. Cambiar su ubicacion es
  una hipotesis de I/O aprobada para medir, no una mejora ya demostrada.

### Pendientes para cerrar el objetivo

1. Incorporar esta formalizacion al candidato, registrar el arbol final con el baseline aprobado
   conservando las 55 entradas externas y actualizar PR161 sin reescribir commits.
2. Medir tres workflows completos consecutivos del mismo head final: init
   Windows <480 s en cada uno; contratos, Ubuntu/Windows, ambas pasadas,
   SDK y Board satisfactorios. Cero muestras aceptadas del candidato local.
3. Conservar todas las muestras fallidas y comparar tambien el job Windows
   completo. Si la ubicacion temporal no basta, continuar sobre el coste medido.
4. La fusion y la verificacion posterior de main/Pages son una etapa distinta.
   Este trabajo no autoriza excepciones de gates, runtime ni protecciones.

Se conservan runtime `74d357f`, timeout 600 s, presupuesto Git seguro de 62
procesos y los perfiles existentes. El [contrato y protocolo de temporales](windows-ci-test-temp.md)
define la siguiente medicion. Los cortes inferiores son evidencia historica;
sus pendientes no deben leerse como una nueva auditoria del main actual.

## Actualizacion posterior del 1 de noviembre de 2026

El [PR 158](https://github.com/MauricioPerera/KDD/pull/158) se integro en
`main` mediante `292f0e53aa50c7836300fafb389baa45dc176f08`, con KG-1 a KG-5
y sus artefactos de cierre. Al preparar esta actualizacion, el
[CI de main](https://github.com/MauricioPerera/KDD/actions/runs/41330505969)
estaba en curso; ese enlace no afirma un resultado futuro. La remediacion de
bootstrap, guard y complejidad aun vive en una rama de trabajo independiente.
La evidencia del corte anterior conserva su SHA y sus resultados originales.

## Corte verificado del 1 de noviembre de 2026

El `main` auditado `f1faf516b0622bd5d91ffb7321580127530aa948` integra
la compatibilidad de contexto v0.3, los contratos de grupo y la validacion
previa de discovery de Pages. El [CI](https://github.com/MauricioPerera/KDD/actions/runs/41291672436)
paso en Ubuntu y Windows con dos pasadas de 1791 IDs por sistema; cada pasada
registro 10 SKIP en Ubuntu y 9 en Windows. El [despliegue](https://github.com/MauricioPerera/KDD/actions/runs/41294269554)
de Pages paso y el sitio publico se comprobo. El total incluye los SKIP y no
mide cobertura de codigo.

La integracion de gobernanza [PR 158](https://github.com/MauricioPerera/KDD/pull/158)
y la remediacion [de auditoria](audit-p1-p2-remediation.md) eran candidatos
en ese corte; el PR 158 se integro despues, segun la actualizacion superior. El corte siguiente conserva su contexto historico.

## Corte verificado del 31 de octubre de 2026

Este corte distingue el resultado publicado de una mejora aun local. Los
conteos y duraciones son evidencia de las revisiones indicadas, no promesas
para ejecuciones futuras.

| Revision | Estado y evidencia |
| --- | --- |
| `main` publicado: [`925128b8`](https://github.com/MauricioPerera/KDD/commit/925128b8ddaba64b25cf17f4c46f8177fd6830c7) | Integra los contratos de grupo del [PR 153](https://github.com/MauricioPerera/KDD/pull/153). El [CI](https://github.com/MauricioPerera/KDD/actions/runs/41263167862) paso los cuatro jobs Ubuntu/Windows; cada sistema ejecuto dos pasadas de 1724 IDs, con 10 SKIP en Ubuntu y 9 en Windows. El [despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/41265652206) paso para ese SHA. |
| Rama local `codex/context-v03-compat`: `f933928b41d4dc2005ef7ffecc55bd28c873aa49` | Implementa [compatibilidad de contexto CCDD v0.3](context-v03-compat.md), sobre el baseline aprobado `366275c9c165073f0423cb482f39fe4df37fce5d`. No esta publicada ni integrada en `main`; su CI remoto y el despliegue posterior aun no se han verificado. |
| Rama local `codex/validate-okf-complexity`: `4eda15e4a64e0aac57ffa3243d2537fe4f797ee4` | Reduccion de complejidad de `validate_okf.py`, con baseline aprobado `369712a82b0ff17292b456cd77a20de56e790aa2`. Conserva dos commits sobre el main anterior `74fcbae`; no tiene PR ni esta integrada en el main de este corte. Su evidencia debe reevaluarse sobre la base de integracion que se elija. |

En la rama local, las cuatro pasadas con el runtime revisado ejecutaron los
mismos **1777 IDs**, sin fallos ni errores: 485,2 y 482,8 s en Windows y 124,0
y 121,2 s en Ubuntu. Las omisiones fueron 9 y 10 por pasada, respectivamente:
ocho casos MCP se ejecutaron aparte con el SDK fijado, `init-project` se
ejecuto en los comandos de contratos y la omision adicional en Ubuntu es un
caso especifico de Windows. Los 139 contratos y sus comandos pasaron en ambos
sistemas; `init-project` tardo 510,7 s en Windows y 113,7 s en Ubuntu, con
limite de 600 s. Board paso sus 70 pruebas y typecheck en ambos sistemas.

Las 53 pruebas nuevas cubren la compatibilidad; tambien se compararon cuatro
contratos existentes con el runner original sin publicar su contenido. Hubo
intentos locales fallidos por la diferencia de PID del lanzador de un venv de
Windows y por fixtures de `actionlint` y `PATH` ausentes en Ubuntu; las
repeticiones anteriores usan entornos corregidos. Los informes detallados
estan en `.agents/logs/context-v03/` y son locales, no evidencia versionada ni
un run de GitHub Actions.

La rama de complejidad de `validate_okf.py` conservo sus limites y registro
dos pasadas satisfactorias de 1709 IDs por sistema, pero tambien dos fallos
anteriores de contencion de procesos en Windows cuya causa no quedo establecida.
Dos repeticiones verdes no explican esos fallos. La evidencia de esa revision
esta en `.agents/logs/validate-okf-complexity-REPORT.md`, solo local.
En cambio, las reducciones del motor de reglas, `task_git.py`,
`verify_quality.py` y `assemble_context.py` ya forman parte del main citado.

Los contratos de grupo publicados componen contratos atomicos y grupos bajo
una referencia explicita y ejecutan sus integraciones; no acreditan por si
solos el Nivel 2 ni la aprobacion de identidad. El adaptador local de contexto
permite `lint`, `assemble` y `diff` como perfil opt-in; no ejecuta proveedores
dinamicos ni verifica firmas de quorum. Su salida declara
`governance_verified: false`. Los detalles y limites estan en
[grupos](group-contracts.md) y [contexto v0.3](context-v03-compat.md).

## Corte historico del 29 de octubre de 2026

El main [`76603cf8`](https://github.com/MauricioPerera/KDD/commit/76603cf867e004d9b1cfc447fa4bc98b66eaf299)
integra el [PR141](https://github.com/MauricioPerera/KDD/pull/141) con sus
cuatro commits originales. El [CI de main](https://github.com/MauricioPerera/KDD/actions/runs/40824973487)
paso en Ubuntu y Windows: dos pasadas de 1662 IDs por sistema, con 10 skips
declarados en Ubuntu y 9 en Windows. El [despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/40828573792)
paso y publico el inventario de ese run.

Board inicia vacio en un proyecto sin tareas, rechaza la seleccion de un
subdirectorio que no es raiz Git y conserva el soporte de worktrees. El
fixture de trazabilidad evita importar un paquete `src` ajeno. Los controles
de Entire del PR141 fallaron por falta de aprobacion del trail; los cinco
checks exigidos por la proteccion de main pasaron y la fusion no modifico
esa proteccion.

## Corte historico del 28 de octubre de 2026

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
seleccion de raiz Git y de aislamiento de fixtures. En este corte aun no
formaban parte del main citado; la actualizacion superior registra su posterior
integracion y CI. Su [integracion Board](board-git.md) describe el flujo.
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
| Contratos de grupo | Componer y ejecutar contratos atomicos e integraciones bajo una referencia explicita; disponible en el main del corte actual. | [Grupos](group-contracts.md) |
| Contexto CCDD v0.3 | Validar, ensamblar y comparar contextos como perfil opt-in, integrado en main. No ejecuta proveedores dinamicos ni acredita firmas de quorum. | [Compatibilidad de contexto](context-v03-compat.md) |
| Task y diario Git | Registrar el avance operativo en nodos de `main`, con una rama de implementación por tarea e historial de transiciones validable. | [Modelo Task](data_models/git-task.md), [tareas con Git](git-tasks.md) |
| CLI y KDD-Board | Operar el mismo coordinador; leer tareas confirmadas de `main` y devolver el commit real de cada cambio de estado. | [CLI](contracts/task-cli.md), [integración del tablero](board-git.md) |
| Bootstrap | Adaptar la plantilla a la identidad del proyecto, retirar ejemplos e historial operativo heredado y preparar el CI de producto. | [Inicializador](contracts/init-project.md), [arranque guiado](contracts/bootstrap-project.md) |
| Política de calidad | Delimitar archivos protegidos y cambios permitidos; ejecutar checks estructurales, funcionales, adversariales y de interfaz según el producto. | [Aprobación de calidad](quality-approval.md) |
| Aceptacion y controles declarados | Comprobar obligaciones, oraculos, controles requeridos y procedencia segun la politica del producto. Su disponibilidad no acredita automaticamente una entrega. | [Aceptacion](acceptance.md), [controles requeridos](required-controls.md), [oraculos revisados](oracle-assurance.md) |
| CI | Ejecutar validación y tablero en Ubuntu/Windows, con runtime revisado fuera del checkout, dos pasadas completas y reportes por ID; exigir calidad de producto en proyectos inicializados. | [Calidad desde el arranque](bootstrap-product-quality-ci.md), [tiempo del CI](ci-runtime.md), [frontera de confianza](ci-audit-remediation.md) |
| Pages | Compilar el sitio real en PR de ambas plataformas y reconstruir al desplegar el SHA de main cuyo CI paso, con cotejo de inventarios de las cuatro pasadas y discovery estricto. | [Build en PR](pages-pr-validation.md), [inventario](pages-ci-inventory.md), [operacion](../site/README.md) |

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
- **Limites del contexto integrado.** La compatibilidad v0.3 ya esta en main.
  Las firmas de quorum y la ejecucion de fuentes dinamicas no estan soportadas
  por ese perfil. Ampliarlas exige un objetivo, contratos y evidencia propios;
  no forma parte de la optimizacion Windows actual.
- **Complejidad integrada y deuda restante.** PR161 ya integra las reducciones
  indicadas en su alcance, incluida `validate_okf.py`. Falta una medicion global
  nueva para priorizar la deuda restante; los recuentos historicos no son una
  auditoria del main actual.
- **Rendimiento Windows.** Publicacion, fusion y verificacion funcional ya
  terminaron. Sigue pendiente demostrar init <480 s en tres CI completos
  consecutivos del mismo head, conservando cobertura, ambas plataformas y
  las dos pasadas. El corte actual registra 515,16 s en main y mantiene el
  objetivo abierto.
- **Proxima validacion de uso.** Ya hay pilotos CLI de una y cuatro tareas con
  dependencias. Falta medir colaboracion concurrente real, requisitos de interfaz
  y coste de revision en un producto mayor. El piloto HTTP automatizado no
  equivale a comprobar un navegador renderizado ni un equipo distribuido.

Los límites técnicos completos se mantienen en
[garantías verificables](verification-guarantees.md). Las ampliaciones de
alcance necesitaran contratos y evidencia propios.
