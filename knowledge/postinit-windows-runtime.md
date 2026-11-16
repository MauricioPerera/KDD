---
type: 'Concept'
title: 'Post-init de Windows en CI'
description: 'Plazo común de las dos particiones de Windows y evidencia de tres intentos consecutivos en main.'
tags: ['ci', 'windows', 'performance', 'bootstrap']
---

# Cierre en main

El [PR #196](https://github.com/MauricioPerera/KDD/pull/196) incorporó la matriz
`postinit_windows` al CI nativo de KDD para PR y pushes a `main`. Los jobs
`Windows post-init (0)` y `Windows post-init (1)` ejecutan en paralelo
[particiones disjuntas](contracts/postinit-windows-partitions.md) de la suite,
cada una en una copia inicializada independiente.

El check `validate (windows-latest)` coteja los dos recibos con el inventario
de una tercera copia inicializada. Exige el mismo run, intento, SHA, árbol y
runtime en la evidencia. La cota se calcula desde el inicio más temprano hasta
el fin más tardío de los dos pasos `Run post-init shard`, más un segundo por
la precisión de los tiempos de GitHub. Así incluye el desfase de arranque.
El check rechaza cotas superiores a 600 s y registra el resultado en
`KDD_POSTINIT_WINDOW`. [Contrato del plazo común](contracts/postinit-windows-common-deadline.md)

## Evidencia de los tres intentos

El push a `main` del commit `04fcd982a366ac18f95832bc6dbca26703f897a0`
generó el run `43858498105`. El intento original y dos repeticiones completas
consecutivas terminaron correctamente con una cota común inferior a 600 s.
En los tres, las particiones acreditaron 1.175 y 1.230 IDs respectivamente,
con el inventario de 2.405 casos completo.

| Intento | Job 0 | Job 1 | Cota común | Evidencia |
| --- | ---: | ---: | ---: | --- |
| 1 | 418 s | 394 s | 419 s | [GitHub Actions](https://github.com/MauricioPerera/KDD/actions/runs/43858498105/attempts/1) |
| 2 | 408 s | 376 s | 409 s | [GitHub Actions](https://github.com/MauricioPerera/KDD/actions/runs/43858498105/attempts/2) |
| 3 | 291 s | 351 s | 352 s | [GitHub Actions](https://github.com/MauricioPerera/KDD/actions/runs/43858498105/attempts/3) |

Cada intento completó dos pasadas generales en Ubuntu y dos en Windows,
todas con los mismos 2.509 IDs y el digest
`c41215d3dd41de8fd6e56d34dec8fc592c42d57fd4927eaa1d2cb414c924caa6`.
Los artefactos `kdd-coverage-43858498105-<intento>-<plataforma>` registraron
`suite_pass=1` para ambos sistemas. Los recibos de las particiones se
publicaron como `kdd-postinit-shard-43858498105-<intento>-<partición>`.

# Ensayo inicial de margen

El ensayo original fijó una meta de menos de 480 s para el comando completo
de [init-project](contracts/init-project.md) en tres workflows consecutivos
del mismo head. Conservó los 600 s operativos, Ubuntu y Windows, y las dos
pasadas generales. Sus mediciones corresponden al perfil de un solo job de
Windows. El cierre de `04fcd98` mide la ventana común de las dos particiones.

## Evidencia de partida

El arbol de `827c1f3a72881468861f15935226940d6f8744f0` agoto 600 segundos en
Windows y paso en una repeticion con 597,395 segundos de unittest para init.
El job completo Windows tardo 48:52. Esa ejecucion acredita funcionalidad,
no un margen estable ni una reduccion del tiempo total.

En diagnosticos locales secuenciales con Python 3.11.15 y Git 2.54 nativo,
el comando instrumentado tardo 439,174 segundos con cuatro workers, 339,656
con seis y 297,281 con ocho. Los tres conservaron los mismos 1.969 IDs y
104 SKIP de la copia inicializada. El perfil directo es diagnostico, no una
muestra del comando estandar en GitHub ni una promesa de equivalencia entre
hosts. CI ya selecciona Git nativo; ese ajuste no es una optimizacion nueva.

Una comprobacion real de aliases del fixture `test_task_committed_artifacts`
resolvio la raiz 4.362 veces: `_key` acumulo 1,145 segundos en una ejecucion
instrumentada de 8,424 segundos. La propuesta de [identidad de raiz](contracts/task-root-identity.md)
reduce ese coste sin adelantar lecturas Git ni cachear refs o resultados nuevos.

## Cambios propuestos en la medicion de partida

El [ensayo de concurrencia](contracts/postinit-windows-concurrency.md)
define el perfil que se medira en el siguiente candidato.

- [Identidad fisica de la raiz](contracts/task-root-identity.md): clave de
  cache por directorio real, observada de nuevo en cada consulta, con fallback
  compatible cuando el sistema no ofrece una identidad util.
- [Perfil post-apply](contracts/init-post-apply-profile.md): ocho workers solo
  en el post-init Windows; cuatro en Ubuntu. Las dos suites ordinarias
  mantienen sus perfiles. El resultado debe medirse de forma completa.
- [Duracion del comando en CI](contracts/postinit-command-timing.md): publicar
  los datos existentes del runtime revisado, sin inferir el tiempo de init
  del paso que ejecuta todos los contratos ni de stdout del producto.

## Verificacion y limites

Conservar los metodos y aserciones anteriores, sus IDs y los SKIP aplicables.
Las pruebas nuevas se contabilizan aparte; los inventarios de la plantilla y
de la copia inicializada se comparan cada uno contra su propia referencia.
Mantener el presupuesto seguro de 62 procesos y los controles de `git replace`,
modos, objetos corruptos, aliases y aislamiento entre repositorios.

La [politica de calidad](quality-approval.md) exige revisar los nuevos contratos
y oraculos antes de adoptar los cambios. Cualquier cambio de runtime requiere
otra revision especifica; no modificar protecciones ni fusionar el PR como
parte de esta optimizacion. Medir tambien el resto del job y el workflow para
no desplazar el coste y atribuirle una mejora inexistente.
