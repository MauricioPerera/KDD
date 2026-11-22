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
