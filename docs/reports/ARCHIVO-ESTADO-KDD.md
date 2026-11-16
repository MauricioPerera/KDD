# Archivo de cortes de KDD

Evidencia histórica del 24 de octubre al 6 de noviembre de 2026. El [estado de KDD](../../knowledge/estado-actual-kdd.md) conserva las referencias a cada corte.

## Corte histórico del 6 de noviembre de 2026, 23:38 UTC

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
[informe versionado](KDD-STATE-2026-11-06-REPORT.md)
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
PR164 agrega el [observador de identidad estable](../../knowledge/process-observer-identity.md):
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

### Pendientes registrados en este corte

1. **Rendimiento Windows.** El objetivo exige init <480 s en tres workflows
   completos consecutivos del mismo head, con ambos sistemas y ambas pasadas
   correctos. La muestra de este corte mide 515,16 s y no cumple ese criterio,
   aunque pasa el timeout de 600 s. El PR midio 339,12 s y su job Windows
   27 min 37 s; son SHA y eventos distintos y no forman una comparacion causal
   ni tres muestras aceptadas. Seguir el [protocolo vigente](../../knowledge/windows-ci-test-temp.md).
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
procesos y los perfiles existentes. El [contrato y protocolo de temporales](../../knowledge/windows-ci-test-temp.md)
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
y la remediacion [de auditoria](../../knowledge/audit-p1-p2-remediation.md) eran candidatos
en ese corte; el PR 158 se integro despues, segun la actualizacion superior. El corte siguiente conserva su contexto historico.

## Corte verificado del 31 de octubre de 2026

Este corte distingue el resultado publicado de una mejora aun local. Los
conteos y duraciones son evidencia de las revisiones indicadas, no promesas
para ejecuciones futuras.

| Revision | Estado y evidencia |
| --- | --- |
| `main` publicado: [`925128b8`](https://github.com/MauricioPerera/KDD/commit/925128b8ddaba64b25cf17f4c46f8177fd6830c7) | Integra los contratos de grupo del [PR 153](https://github.com/MauricioPerera/KDD/pull/153). El [CI](https://github.com/MauricioPerera/KDD/actions/runs/41263167862) paso los cuatro jobs Ubuntu/Windows; cada sistema ejecuto dos pasadas de 1724 IDs, con 10 SKIP en Ubuntu y 9 en Windows. El [despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/41265652206) paso para ese SHA. |
| Rama local `codex/context-v03-compat`: `f933928b41d4dc2005ef7ffecc55bd28c873aa49` | Implementa [compatibilidad de contexto CCDD v0.3](../../knowledge/context-v03-compat.md), sobre el baseline aprobado `366275c9c165073f0423cb482f39fe4df37fce5d`. No esta publicada ni integrada en `main`; su CI remoto y el despliegue posterior aun no se han verificado. |
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
[grupos](../../knowledge/group-contracts.md) y [contexto v0.3](../../knowledge/context-v03-compat.md).

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
[diagnostico historico de CI](../../knowledge/ci-diagnostico-2026-10.md) aporta contexto sin
prometer que las mediciones sean comparables causalmente.

La auditoria posterior identifico mejoras de arranque de Board sin Git, de
seleccion de raiz Git y de aislamiento de fixtures. En este corte aun no
formaban parte del main citado; la actualizacion superior registra su posterior
integracion y CI. Su [integracion Board](../../knowledge/board-git.md) describe el flujo.
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
