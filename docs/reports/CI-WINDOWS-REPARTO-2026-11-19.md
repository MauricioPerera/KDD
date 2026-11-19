# Cierre del reparto de la validación de Windows

El [PR #203](https://github.com/MauricioPerera/KDD/pull/203) repartió el gate de
contratos y las suites de Windows entre los dos runners existentes. En `main`,
los tres intentos consecutivos de `f15495a` pasaron y la mediana hasta completar
ambos checks de Windows bajó de **50:56 a 37:09** frente a `f512f71`. El ahorro
de pared fue de **13:47 (27,1 %)**. [CI de `f15495a`](https://github.com/MauricioPerera/KDD/actions/runs/44571446882) · [CI de `f512f71`](https://github.com/MauricioPerera/KDD/actions/runs/44465067255)

## Reparto en el CI nativo

| Job | Runner | Trabajo |
| --- | --- | --- |
| `board (windows-latest)` | Windows | El rol `win_contracts` ejecuta los comandos de contratos con cuatro workers, mantiene `init-project` exclusivo y ejecuta el typecheck y las pruebas de Board. |
| `Windows validation work` | Windows | El rol `win_suite` ejecuta ambas pasadas con seis workers, mide la cobertura en la primera y comprueba los recibos del post-init. |
| `validate (windows-latest)` | Ubuntu | Espera a los dos productores. Comprueba la procedencia y los hashes de sus recibos y de la cobertura, y concilia el inventario de las dos pasadas antes de publicar el check requerido. |

Los dos productores Windows trabajan en paralelo. El post-init sigue en sus dos
jobs independientes con un plazo común de 600 s. Ubuntu conserva su perfil y
sus dos pasadas. El reparto se aplica a los PR y al push a `main` del workflow
nativo de KDD. El workflow reutilizable conserva su perfil completo por sistema.
[Contrato de reparto](../../knowledge/contracts/ci-windows-board-routing.md) · [Contrato de recibos](../../knowledge/contracts/ci-windows-board-receipts.md) · [Plazo de post-init](../../knowledge/contracts/postinit-windows-common-deadline.md)

## Tres intentos consecutivos en main

El run `44571446882` probó el mismo commit
`f15495a18ecb28993d7059c757d87d5387775c6f` y árbol
`02aebe7b06d272f3cd7a12ee7cda5a4299e64f8d` en los intentos 1, 2 y 3. El
tiempo de pared se mide desde el inicio del intento hasta que terminan ambos
checks requeridos de Windows. Incluye la espera de los jobs y la comprobación
final en Ubuntu.

| Intento | Hasta ambos checks de Windows | Post-init de Windows | Ubuntu | Windows |
| --- | ---: | ---: | ---: | ---: |
| [1](https://github.com/MauricioPerera/KDD/actions/runs/44571446882/attempts/1) | 37:09 | 436 s | 2 × 2.600 casos | 2 × 2.600 casos |
| [2](https://github.com/MauricioPerera/KDD/actions/runs/44571446882/attempts/2) | 22:19 | 422 s | 2 × 2.600 casos | 2 × 2.600 casos |
| [3](https://github.com/MauricioPerera/KDD/actions/runs/44571446882/attempts/3) | 38:35 | 444 s | 2 × 2.600 casos | 2 × 2.600 casos |

Los cuatro reportes de suite de cada intento acreditan el mismo inventario de
2.600 IDs. En la primera pasada de cada intento, la cobertura de líneas fue
de **73,78 %** en Ubuntu (14.297 de 19.377) y **75,31 %** en Windows
(14.592 de 19.377). Los recibos de los dos jobs de post-init acreditan 1.228 y
1.268 IDs dentro de la ventana común en cada intento. Los tres tiempos de
post-init quedaron por debajo de 600 s.

## Comparación de tiempos

| Serie | Evento | Casos por pasada | Tiempos de pared por intento | Mediana | Diferencia de `f15495a` |
| --- | --- | ---: | --- | ---: | ---: |
| [`main f512f71`](https://github.com/MauricioPerera/KDD/actions/runs/44465067255) | Push a `main` | 2.573 | 51:38, 38:49, 50:56 | 50:56 | 13:47 menos (27,1 %) |
| [CI del PR #199](https://github.com/MauricioPerera/KDD/actions/runs/44210301823) | Pull request | 2.563 | 38:34, 37:03, 36:42 | 37:03 | 6 s más (0,27 %) |
| [`main f15495a`](https://github.com/MauricioPerera/KDD/actions/runs/44571446882) | Push a `main` | 2.600 | 37:09, 22:19, 38:35 | 37:09 | Referencia del cierre |

La muestra más lenta de `f15495a` tardó 38:35, por debajo de los 38:49 de la
más rápida de `f512f71`. Frente al PR #199, la mediana quedó 6 s por encima. Los
eventos y los inventarios de cada revisión delimitan la comparación histórica.

La mediana de la suma de tiempo de los dos productores Windows fue **48:18**,
frente a **52:52** en `f512f71` y **38:41** en el PR #199. Esta suma permite
comparar el uso de runners en validación y Board, con las particiones de
post-init medidas por separado.

Antes de fusionar, el [intento 3 del PR #203](https://github.com/MauricioPerera/KDD/actions/runs/44545887765/attempts/3)
falló al agotar el plazo de 2 s de una prueba de deduplicación en la primera
pasada de Windows. Los tres intentos consecutivos del cierre corresponden al
run de `main` indicado arriba.
