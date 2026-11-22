# Cierre del lanzamiento directo en el CI de Windows

El [PR #205](https://github.com/MauricioPerera/KDD/pull/205) integró el
lanzamiento directo en `main`. Los tres intentos del mismo SHA y runtime
pasaron con Ubuntu y Windows. La mediana hasta completar los checks de
Windows bajó de **26:46 a 25:07** frente a la ejecución anterior de
`main`, un ahorro observado de **1:39 (6,16 %)**.
[CI de referencia](https://github.com/MauricioPerera/KDD/actions/runs/44613234861/attempts/1)

## Lanzamiento y contención

En Windows compatible, `scripts/process_tree.py` crea el proceso objetivo
con `CreateProcessW` y el atributo `PROC_THREAD_ATTRIBUTE_JOB_LIST`. El
objetivo se incorpora al Job Object propio al crearse, antes de ejecutar
su código, y su padre directo es el proceso que llama al lanzador. Así se
elimina el intérprete intermedio. Se conservan la entrada y salida, el
entorno, los códigos de salida, la limpieza y el aislamiento entre
invocaciones, incluidas las que corren bajo un Job exterior.

La ruta anterior se activa si Windows confirma que el atributo no está
disponible antes de intentar crear el objetivo. Los demás errores se
propagan. En POSIX se conserva la ejecución directa con su grupo de
procesos. [Contrato del lanzamiento](../../knowledge/contracts/process-job-at-creation.md) ·
[Contrato de terminación](../../knowledge/contracts/process-exit-barrier.md)

## Tres intentos consecutivos en main

El push de `4172d7193dcb481e226407ea696581f8918a3fcf` generó el run
`44923750898`. El intento original y dos repeticiones completas usaron
ese checkout y el runtime `39e402e4377aa5e97947888b9b5934202af8302e`.
El runtime fija el lanzador revisado en el bundle que materializa el
workflow. [Referencia de runtime](https://github.com/MauricioPerera/KDD/tree/kdd-runtime-windows-job-39e402e)

| Intento | Hasta ambos checks de Windows | Pasadas Ubuntu | Pasadas Windows | Post-init Windows |
| --- | ---: | ---: | ---: | ---: |
| [1](https://github.com/MauricioPerera/KDD/actions/runs/44923750898/attempts/1) | 19:33 | 5:20 / 3:33 | 10:31 / 7:22 | 416 s |
| [2](https://github.com/MauricioPerera/KDD/actions/runs/44923750898/attempts/2) | 25:07 | 6:33 / 4:04 | 13:44 / 9:30 | 399 s |
| [3](https://github.com/MauricioPerera/KDD/actions/runs/44923750898/attempts/3) | 25:40 | 6:28 / 4:00 | 13:30 / 9:58 | 453 s |

Cada una de las dos pasadas de Ubuntu y Windows acreditó los mismos
**2.618 IDs**, con digest
`0b3c763ea4d7750a90f36cd92a57af7a94df3c90ddba2cc7bcc426f1f35b7b15`.
Los artefactos de cobertura de líneas y ramas corresponden a la primera
pasada en ambos sistemas. Los dos grupos de post-init de Windows
acreditaron 1.238 y 1.276 IDs por intento. Las tres cotas quedaron por
debajo de 600 s. [Plazo común](../../knowledge/contracts/postinit-windows-common-deadline.md)

El despliegue posterior al tercer intento verificó ambos inventarios y
publicó los 2.618 casos en Pages. Al concluir la serie se restauró la
referencia compartida `74d357f7099651b9b39dc8088f725183a672ec94`. Los
resultados de esta tabla corresponden a las ejecuciones fijadas a
`39e402e`. [Despliegue verificado](https://github.com/MauricioPerera/KDD/actions/runs/44930619583)

## Comparación con dae79b1

El tiempo de pared va desde el inicio del intento hasta la finalización
de `board (windows-latest)` y `validate (windows-latest)`. La misma
medida dio **26:46 (1.606 s)** en
`dae79b1f9be9490f14a9441a8324788e978f58e9`. En `4172d71` los tres
intentos cerraron por debajo de esa referencia y la mediana fue
**25:07 (1.507 s)**.

El ahorro del **6,16 %** compara tres intentos del candidato con una sola
ejecución del `main` anterior. Mide la diferencia observada en el CI
completo de Windows, con los demás cambios del PR y la variación entre
runners. El efecto aislado del lanzamiento directo requiere una
comparación controlada. [CI de `dae79b1`](https://github.com/MauricioPerera/KDD/actions/runs/44613234861/attempts/1)

## Runtimes en 00e1af7

La comparación fijó `main` en `00e1af78c298e0d8f960040cdb7727c5c091640f`
y repitió el workflow completo del run `44948707100`. Las tres parejas
originales alternaron el orden de ejecución, con `74d357f` primero en las
parejas 1 y 3 y `39e402e` primero en la pareja 2. El tiempo de Windows se
mide desde el inicio del intento hasta que terminan ambos checks requeridos,
`board (windows-latest)` y `validate (windows-latest)`.
[Run de main](https://github.com/MauricioPerera/KDD/actions/runs/44948707100)

| Intento | Runtime | Hasta ambos checks de Windows | Pasadas Ubuntu | Pasadas Windows | Post-init Windows | Pages |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| [3](https://github.com/MauricioPerera/KDD/actions/runs/44948707100/attempts/3) | `74d357f` | 25:25 | 6:33 / 4:01 | 13:43 / 9:41 | 382 s | [Verificado](https://github.com/MauricioPerera/KDD/actions/runs/44957593868) |
| [4](https://github.com/MauricioPerera/KDD/actions/runs/44948707100/attempts/4) | `39e402e` | 35:49 | 4:20 / 3:07 | 19:26 / 14:02 | 378 s | [Verificado](https://github.com/MauricioPerera/KDD/actions/runs/44960665349) |
| [5](https://github.com/MauricioPerera/KDD/actions/runs/44948707100/attempts/5) | `39e402e` | 27:21 | 4:33 / 3:15 | 14:32 / 10:45 | 406 s | [Verificado](https://github.com/MauricioPerera/KDD/actions/runs/44963033744) |
| [6](https://github.com/MauricioPerera/KDD/actions/runs/44948707100/attempts/6) | `74d357f` | 19:51 | 5:18 / 3:26 | 10:29 / 7:44 | 398 s | [Falló el despliegue](https://github.com/MauricioPerera/KDD/actions/runs/44964701316/attempts/1) |
| [7](https://github.com/MauricioPerera/KDD/actions/runs/44948707100/attempts/7) | `74d357f` | 36:14 | 6:30 / 3:59 | 19:56 / 13:59 | 379 s | [Verificado](https://github.com/MauricioPerera/KDD/actions/runs/44967801816) |
| [8](https://github.com/MauricioPerera/KDD/actions/runs/44948707100/attempts/8) | `39e402e` | 34:50 | 4:44 / 3:17 | 19:02 / 13:29 | 409 s | [Verificado](https://github.com/MauricioPerera/KDD/actions/runs/44970679819) |
| [9, recuperación](https://github.com/MauricioPerera/KDD/actions/runs/44948707100/attempts/9) | `74d357f` | 25:17 | 5:32 / 3:33 | 13:39 / 9:42 | 403 s | [Verificado](https://github.com/MauricioPerera/KDD/actions/runs/44973260562) |

Cada uno de los siete CI completó dos pasadas en Ubuntu y Windows, con
los mismos **2.623 IDs por pasada** y el digest
`aaf9c5d208781288c8327d20f920bdb842847489108d44684e1bbb2aa7edc90b`.
Los reportes de cobertura de líneas y ramas correspondieron a la primera
pasada de cada sistema. Las ventanas del post-init de Windows quedaron
entre **378 y 409 s**, por debajo del plazo común de 600 s.
[Contrato del plazo común](../../knowledge/contracts/postinit-windows-common-deadline.md)

### Diferencia en Windows

Con tres despliegues verificados por runtime, las medianas fueron **25:25
(1.525 s)** con `74d357f` y **34:50 (2.090 s)** con `39e402e`. La
diferencia observada fue de **9:25 (565 s, 37,05 % más)**. En las tres
parejas originales, `39e402e` tardó 10:24 más, 7:30 más y 1:24 menos,
respectivamente. La variación entre runners limita cuánto de la
diferencia se puede atribuir al runtime.

### Recuperación de Pages y runtime activo

El CI del intento 6 pasó y el build de Pages verificó ambos inventarios
con `74d357f`. El paso de despliegue no encontró el artefacto
`github-pages` que el paso de subida acababa de finalizar. Al repetir
solo Pages, la descarga del inventario Ubuntu del intento 6 falló porque
el artefacto ya no aparecía en la API. El tiempo de Windows de ese CI se
conservó en la serie original. [Fallo inicial](https://github.com/MauricioPerera/KDD/actions/runs/44964701316/attempts/1) ·
[Reintento de Pages](https://github.com/MauricioPerera/KDD/actions/runs/44964701316/attempts/2)

El intento 9 repitió el CI completo con `74d357f` sobre el mismo SHA y
completó el tercer despliegue verificado para ese runtime. La mediana de
Windows fue 25:25 tanto en los tres CI originales de `74d357f` como en
los tres que completaron Pages.
[Despliegue de recuperación](https://github.com/MauricioPerera/KDD/actions/runs/44973260562)

Al cierre se verificó que `KDD_TRUSTED_RUNTIME_REF` quedó fijada a
`39e402e4377aa5e97947888b9b5934202af8302e`. El despliegue de
recuperación quedó asociado a `74d357f`, el runtime que registraron los
inventarios del intento 9.
[Vinculación de Pages al CI productor](../../knowledge/pages-ci-inventory.md#comprobaciones-antes-de-publicar)
