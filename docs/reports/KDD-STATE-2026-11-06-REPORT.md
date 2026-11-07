# Estado integrado de KDD: 6 de noviembre de 2026

Este informe documenta `main` en `0ac8666d9dc686e749890ca73bf3a736878c377a`,
verificado a las 23:38 UTC. El [estado canonico](../../knowledge/estado-actual-kdd.md)
enlaza las capacidades, sus contratos, limites y pendientes. Los resultados
de este informe corresponden a ese codigo; los cambios documentales que lo
registran no tienen una nueva ejecucion remota propia.

## Integracion y confianza

| Elemento | Referencia verificada |
| --- | --- |
| PR161 | [Fusionado](https://github.com/MauricioPerera/KDD/pull/161), 41 commits originales, merge `d367208a8c04479c53906076bb292d032b52ad9d` |
| PR164 | [Fusionado](https://github.com/MauricioPerera/KDD/pull/164), un commit original `0fb9e41ec7f538bf096a45b9562007d821061cdb` |
| Main final | `0ac8666d9dc686e749890ca73bf3a736878c377a`, padres `d367208a8c04479c53906076bb292d032b52ad9d` y `0fb9e41ec7f538bf096a45b9562007d821061cdb` |
| Arbol final | `ee04fcc150c5a81efd7a2b4753c3fa7f37796878`, igual al arbol probado en PR164 |
| Baseline del arbol | `0fb9e41ec7f538bf096a45b9562007d821061cdb`, aprobado explicitamente por el usuario |
| Runtime aprobado | `74d357f7099651b9b39dc8088f725183a672ec94`, conservado |

Los cinco checks requeridos de PR164 pasaron antes de fusionar. Entire Gates
fallaba por falta de aprobacion del trail; el usuario autorizo una excepcion
puntual para ese PR. Ningun control se desactivo ni se edito. Se verificaron
las protecciones, strict, rulesets y las 57 entradas del registro externo
sin cambios despues de la fusion. El main local quedo limpio y sincronizado.

## Ejecuciones remotas observadas

| Observacion | PR164 | Main posterior |
| --- | --- | --- |
| CI | [42304707531](https://github.com/MauricioPerera/KDD/actions/runs/42304707531), intento 1, SUCCESS | [42308617660](https://github.com/MauricioPerera/KDD/actions/runs/42308617660), intento 1, SUCCESS |
| Evento / head | pull_request / `0fb9e41ec7f538bf096a45b9562007d821061cdb` | push / `0ac8666d9dc686e749890ca73bf3a736878c377a` |
| Checkout probado | `fa08f86e5dac1b8fed70507d9462fcda39cf1288` | `0ac8666d9dc686e749890ca73bf3a736878c377a` |
| Job Windows | 1657 s (27 min 37 s) | 2352 s (39 min 12 s) |
| Init Windows | 339,118931 s | 515,1589716 s |
| Job Ubuntu | 518 s (8 min 38 s) | 531 s (8 min 51 s) |
| Init Ubuntu | 145,520605131 s | 153,374700777 s |

En ambas observaciones pasaron los cuatro jobs funcionales. Cada sistema
ejecuto dos pasadas con los 2118 IDs exactos, 9 SKIP anteriores en Windows y
10 en Ubuntu, cero fallos/errores/omisiones de fixture. El inventario incluye
los SKIP y no constituye una medida porcentual de cobertura de codigo.

El post-init de main ejecuto 2014 casos de 182 modulos, con 101 SKIP en Windows
y 102 en Ubuntu. Los cinco casos nuevos se ejecutaron sin SKIP en ambos
contextos. Board paso 86/86 por sistema; el perfil genuino MCP ejecuto ocho
casos por sistema sin SKIP. Se conservaron las dos pasadas, sus limites y los
19 gates; la validacion estructural del arbol contiene 186 contratos.

El fallo inicial de contencion del CI de PR161 permanece en la
[primer intento del run 42283846624](https://github.com/MauricioPerera/KDD/actions/runs/42283846624/attempts/1).
Su segundo intento paso. La observacion tardia de un PID no identifica al
objeto original: no se deduce de ese log una fuga probada ni una causa
retrospectiva. El [protocolo corregido](../../knowledge/process-observer-identity.md)
conserva objetos nativos antes del exit y verifica fugas deliberadas y vecinos.

## Pages y procedencia del inventario

El [run 42313182858](https://github.com/MauricioPerera/KDD/actions/runs/42313182858),
intento 1, completo build y despliegue de main. El deployment `7613322027`
declaro success para `0ac8666d9dc686e749890ca73bf3a736878c377a`.
El build descargo los dos manifiestos del CI `42308617660`, intento 1,
cotejo las cuatro pasadas y realizo discovery estricto.

La [web publica](https://mauricioperera.github.io/KDD/) respondio HTTP 200 y
enlazo ese run exacto, con 2118 IDs y 19 gates. El build declaro
`inventory_source: ci-verified`; el digest de IDs, con LF final, es
`5679d5bff02314486c9bc9c724174c45407f143c74c29ead403b3310488fcb8a`.

La [evidencia estructurada](KDD-STATE-2026-11-06-EVIDENCE.json) conserva las
comprobaciones de integracion, CI y Pages realizadas al cerrar la fusion.
Es un registro documental de esas observaciones. No reemplaza un oraculo,
una referencia aprobada ni la aceptacion por obligacion de otro producto.

## Resultado y pendientes

La entrega funcional esta integrada y verificada. El objetivo de rendimiento
requiere tres workflows completos consecutivos del mismo head con init Windows
<480 s. La muestra actual de main, 515,16 s, incumple ese criterio y pasa el
limite de seguridad de 600 s. Los dos runs anteriores tienen SHA y eventos
distintos; no son un A/B controlado ni prueban un ahorro causal.

Continuan pendientes esa aceptacion, otra medicion global de la deuda de
complejidad y la evaluacion de colaboracion/productos de mayor escala. La
correccion del observador tiene regresiones deterministas y ejecuciones
verdes; dos observaciones no prueban ausencia universal de intermitencia.
El [estado canonico](../../knowledge/estado-actual-kdd.md) separa estos limites
de las capacidades integradas y conserva todos los cortes historicos.
