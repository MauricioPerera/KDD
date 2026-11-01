# CONTRACT-34 - Cierre mecanico de las brechas de gobierno KDD - REPORT

Fecha: 2026-11-01
Spec: `specs/CONTRACT-34-kdd-governance-closure.md`
CI: https://github.com/MauricioPerera/KDD/actions/runs/41284090752
Commit de integracion citado: `1aaa19e66727066a2c3f064d6c16bad04b2501f6`.
Baseline externo: `b8f4e105320c6715f1df7d62590b359090a3f17f`.

El run citado termino correctamente antes de crear este cierre. Desde ese
commit solo cambian este reporte, su JSON, los checkboxes de la spec y CHANGELOG.
El propio run del cierre no se usa para certificarse.

## Resultado por criterio

| ID | Estado | Evidencia |
| --- | --- | --- |
| AC-1 | verified_in_ci | https://github.com/MauricioPerera/KDD/actions/runs/41284090752 |
| AC-2 | verified_in_ci | https://github.com/MauricioPerera/KDD/actions/runs/41284090752 |
| AC-3 | verified_in_ci | https://github.com/MauricioPerera/KDD/actions/runs/41284090752 |
| AC-4 | verified_in_ci | https://github.com/MauricioPerera/KDD/actions/runs/41284090752 |
| AC-5 | verified_in_ci | https://github.com/MauricioPerera/KDD/actions/runs/41284090752 |
| CI-1 | verified_in_ci | https://github.com/MauricioPerera/KDD/actions/runs/41284090752 |

## Entregas comprobadas

| Entrega | Comportamiento observado | CI de implementacion |
| --- | --- | --- |
| KG-1 | Perimetro aprobado antes de finish y al auditar historial; atribucion Git, integridad y legado explicito | https://github.com/MauricioPerera/KDD/actions/runs/41239179528 |
| KG-2 | Contrato completo y runner por operacion; lectura historica Git y TASK_PERIMETER seguro como 409 | https://github.com/MauricioPerera/KDD/actions/runs/41243512201 |
| KG-3 | Aserciones separadas de errores/inconclusos; contramuestras exactas aprobadas 2x, estructura y recibos | https://github.com/MauricioPerera/KDD/actions/runs/41252212507 |
| KG-4 | Controles requeridos 2x, cobertura positiva y version medida; runtime no soportado bloquea | https://github.com/MauricioPerera/KDD/actions/runs/41256786660 |
| KG-5 | Fuente/entrega identificadas; contexto requerido incompleto bloquea; enlaces Git aceptados y limpieza opcional exacta | https://github.com/MauricioPerera/KDD/actions/runs/41264496192 |

El CI citado verifica la integracion conjunta: 154 contratos y
dos suites de 1944 casos por sistema con inventario identico
`5291251c4ad5ed11e8889b87a15195154229d1b835da420caae9cda2b69443fd`, sin fallos, errores u omisiones de fixture.
El run citado corresponde al intento 1.
Los SKIP normales permanecen explicitos: 10 en Ubuntu y 9 en Windows por pasada.
El board pasa en ambos sistemas. Los comandos de AC-1/AC-2 pasan como oraculos;
AC-3 valida contratos/nodos, AC-4 ejecuta los contratos de todas las entregas y
AC-5 conserva task-git-complexity y las fronteras aprobadas.

La regresion local de KG-5 completo 118 casos por sistema, incluida la suite de
una copia inicializada. Ledger, contexto y budgets reales se observaron 2x por
sistema sobre el commit publicado. El ledger conserva dos entradas aceptadas
segun 2eb28774b7043ff043ea33d141254604603a66db; sus enlaces a tests declaran
reference_verified=true y execution_observed=false. El contexto conserva
fuentes/fragmentos reales, hashes de texto LF comparables y hashes fisicos
verificados por checkout. Lecturas de filesystem/runtime mantienen git_commit=null.

Mediciones de KG-5: 53 funciones de contexto bajo 10/4/150/5, 24 del lector bajo
12/4/150/5 y 16 del inicializador dentro de los limites aprobados, sin elevarlos.
El alcance Python AST no mide lambdas, memoria, latencia, semantica ni aislamiento.

## Aprobaciones, integridad y resultados conservados

Los baselines humanos se conservan: 6bcb5e78, 4e698f52, 6ca1b323, 44695e90,
17800863, d10ae371, 2eb28774, 8dad3baf, 178f6889 y b8f4e105. La referencia vigente de main b39bec5 se conserva en la union. Todos los contratos/oraculos coinciden
con la referencia completa aprobada del CI. La extension de KG-1 reviso el conteo
de specs del inicializador y agrego la comprobacion de la ruta 34. KG-5 reviso
tres expectativas exactas de ese mismo oraculo; sus sellos se actualizaron con
los diffs aprobados. La extension separada 178f6889 reviso una unica expectativa
de test_validate_completion y su sello: permite un PASS solo ante la ruta
exacta REPORT34, conserva findings vacios, FAIL=0 y los 33 SKIP. Los 17 IDs y
las demas aserciones de ese modulo permanecen intactos. No se cambiaron otros
oraculos anteriores. La
correccion separada del nuevo fixture cambia solo su tarea y sello, conservando
IDs y todas las aserciones. Los 33 pares historicos y digests permanecen intactos:
se reportan como SKIP, sin certificarlos retrospectivamente.

El primer CI de KG-5, 41263994076, rechazo la topologia con TASK_BASELINE antes
de las suites completas. La integracion de reemplazo parte de KG-4, importa el
baseline previo y reproduce los parches exactos; conserva el arbol de fuente
f0d9e539994d2a33ff1386275f6d7abe8727acb9 y las ramas/commits originales. Tambien
se conserva el timeout inicial Windows de KG-2, cuya repeticion paso sin cambiar
fuente, oraculos, workflows o limites. En el run 41264496192, el primer intento
Windows agoto los 600 segundos de init-project; la repeticion de los jobs fallidos
termino correctamente sobre el mismo commit. Ubuntu y los boards ya habian
pasado. El diagnostico local posterior completo los 16 casos de inicializacion
en 897.187 segundos: es una observacion funcional y de tiempo local, no una
certificacion CI ni cumplimiento del limite de 600 segundos. No se elevaron
limites ni se cambiaron fuentes, oraculos o workflows para repetir el CI.
Se conservan fases rojas, controles sanos,
fallos de preparacion del runtime local y probes conocidos bajo .agents/logs/.

El primer cierre, commit 226d4d460312d5fd3533db801305c90f811daf52, encontro
en el CI 41272460158 la expectativa historica PASS=0 del oraculo de completion:
Ubuntu ejecuto 147 contratos, 146 pasaron y ese oraculo fallo una asercion con
PASS=1, FAIL=0, SKIP=33. Windows quedo cancelado al sustituirse el run y no se
cuenta como verificacion; ambos boards pasaron. Se conservan los cuatro logs.
La correccion exacta fue aprobada antes de integrarla. Se reabrio el cierre en
c8662a1e5061e59f79f833f8170b952c41213f49 y se aplico solo el parche aprobado en
9cadacb32b3a644dac358a27037416ea3d437d12. El CI citado actual se completo con ese
oraculo antes de volver a crear los cuatro artefactos; produccion no cambio.
El intento 1 del CI 41273667316 agoto 600 segundos en init-project Windows;
los otros 146 contratos, incluido completion corregido, pasaron. Ubuntu y los
boards terminaron correctamente. Se conservo ese intento y se solicito repetir
solo los jobs fallidos, sin cambiar fuentes, oraculos, workflows o limites.
Ningun timeout se cuenta como PASS; el cierre usa solo el run citado terminado.
La compatibilidad fue observada dos veces por sistema en ocho escenarios:
176 ejecuciones, ocho fallos de asercion esperados y 168 positivos por sistema,
sin errores ni SKIP de tests. Legado alterado, evidencia invalida y un segundo
cierre valido 35 siguen rechazados; estos probes son conocidos.

El baseline original 8dad3baf esta retenido en origin mediante
`refs/tags/codex/reviewed/kg5-baseline-8dad3baf`; esa referencia conserva la
propuesta ya aprobada y no representa una release ni otra aprobacion.
La extension 178f6889 se conserva igualmente en
`refs/tags/codex/reviewed/completion-baseline-178f688`. La
integracion debe conservar la ascendencia Git de los registros aprobados del
ledger: eliminarla mediante squash haria fallar la comprobacion de enlaces.

Los checkpoints anteriores de la sesion se verificaron contra origin con
las nueve aprobaciones anteriores y cola vacia. La decima respuesta selecciona
el baseline combinado b8f4e105. El checkpoint del nuevo cierre se comprobara
contra origin al publicarlo; sus ID, objeto y registros reales se conservan
en la evidencia operativa sin atribuirle datos futuros a un snapshot anterior.

## Integracion con el main vigente

El main d4b95583c904461439ceccfe97268b2e9e1e76ee incorporo Context v0.3, Group Contracts y discovery de Pages
despues del candidato KG cedd3bd7236e14d1330e16b0cc032c33c8442bcc. El merge 1aaa19e66727066a2c3f064d6c16bad04b2501f6 conserva ambos como padres y
2eb28774b7043ff043ea33d141254604603a66db como antecesor real del ledger.
Sus dos entradas se verificaron dos veces por sistema sobre ese merge, sin
cambiar HEAD, indice o referencias; no se afirma ejecucion por enlaces.

Los 329 archivos de contratos/pruebas son una union literal de las referencias
externas b39bec5ca00a8a5555b0c4f4f67dfefc8d2a5258 y
178f688961445123e92bbf8152af3a7de32dbf94. La persona revisora selecciono
b8f4e105320c6715f1df7d62590b359090a3f17f antes de registrar el arbol y lanzar CI. No se editaron oraculos,
sellos, IDs, aserciones o limites para integrar las dos ramas.

El ensamblador permanece byte a byte como el KG-5 verificado y pasa tambien
los once casos de complejidad del main con el mismo limite 10/4. Context v0.3,
Group Contracts, validate_okf, los locks y workflows permanecen como en main.
El indice conserva ambos apendices. Windows y Ubuntu ejecutaron dos pasadas
de 195 controles de integracion, sin fallos, errores o SKIP, antes del CI completo.

El cierre anterior se reabrio para no atribuir los cambios nuevos de main a
su CI antiguo. El run citado arriba termino antes de regenerar solamente
spec34, este reporte, su JSON y CHANGELOG. El CI del cierre y el CI de main
se verificaran adicionalmente; este archivo no se usa para certificar su run.

## Frontera de responsabilidad

| El codigo comprueba | La revision humana decide |
| --- | --- |
| Permisos, integridad, versiones y controles observados | Alcance, requisitos, riesgos y restricciones obligatorias |
| Mecanismo y cobertura soportados; rechazo sin soporte | Limites adecuados y suficiencia de oraculos |
| Fuentes/fragmentos y relaciones Git aceptadas | Pertinencia, comprension y coherencia semantica |

Los probes adicionales son conocidos; no son evaluacion independiente. Esa
evaluacion y la generalizacion siguen pendientes de revision humana y no se
afirman. Un campo de texto no autentica a una persona, un hash de test no prueba
su ejecucion, entregar contexto al API no acredita recepcion/comprension del
modelo y AST/Git no son sandbox de runtime. La estabilidad cubre cambios
persistentes observados, no un snapshot atomico ni todos los cambios hostiles
transitorios. El bundle historico sigue en cinco modulos y el auditor advisory
conserva su alcance. El usuario autorizo integrar mediante merge normal y verificar el CI del
commit efectivo de origin/main. Este reporte registra el candidato antes de
esa operacion; los resultados posteriores se conservan con su SHA y run reales.
