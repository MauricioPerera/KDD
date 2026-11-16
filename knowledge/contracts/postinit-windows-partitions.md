---
type: 'Task Contract'
title: 'Particiones completas del post-init de Windows'
description: 'Ejecutar cada modulo en una de dos copias inicializadas y conservar el inventario completo.'
tags: ['ci', 'windows', 'bootstrap', 'integration']
task: postinit-windows-partitions
intent: 'Repartir el trabajo real de post-init de Windows conservando casos, descubrimiento y contencion.'
target: scripts/ci_postinit_shards.py
signature: 'python scripts/ci_postinit_shards.py suite --repo-root DIR --shard 0|1 --report-json FILE'
test_command: 'python -m unittest tests.test_ci_postinit_shards'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  params_max: 4
tests: tests/test_ci_postinit_shards.py
tests_sha256: '763cd35fbc775185277ca648b36da39c38b45023beebc8b83c46fa95030873a4'
oracle_files: ['tests/test_ci_postinit_shards.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/init_project.py', 'scripts/bootstrap_transaction.py', 'scripts/run_test_suite.py', 'scripts/process_tree.py', 'scripts/validate_contracts.py', 'scripts/validate_okf.py']
touch_only: ['scripts/ci_postinit_shards.py', 'scripts/init_post_apply_suite.py', 'tools/ci/postinit-windows-shards.json']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent

El [ensayo aislado del PR 196](https://github.com/MauricioPerera/KDD/actions/runs/43798481708/attempts/1)
agoto el comando completo con 59 resultados de 227 modulos. La autorizacion
permite dos jobs de Windows dentro del [plazo comun](postinit-windows-common-deadline.md).
La particion conserva el [perfil y preparacion de la copia](init-post-apply-profile.md).

## Interface

En modo explicito, el fixture completo sigue aplicando init y lanzando
`scripts/init_post_apply_suite.py`. El entorno del job define
`KDD_POSTINIT_SHARD` con 0 o 1. El launcher delega esa variante en
`scripts/ci_postinit_shards.py suite`, que usa el mismo discovery y workers
aislados de run_test_suite, y su reconciliacion habitual. En Windows se
conservan diez workers por job. El control de integracion permite ejercitar
tambien la misma variante con cuatro workers en Ubuntu.

Leer `tools/ci/postinit-windows-shards.json` en la copia inicializada. Es
`{"schema_version":1,"groups":[[...],[...]]}`, con nombres de modulo,
unicos en la union. Las dos listas se derivan del perfil observado y de los
costes locales para modulos faltantes. Modulos descubiertos que aun no
figuran se asignan por paridad del primer byte del SHA-256 de su nombre UTF-8.
Las listas guian el reparto. El discovery completo determina el universo.
Rechazar inventario vacio, duplicado, ambiguo o una particion vacia.
Los workers atienden cada lista en el orden medido de mayor coste primero,
seguida de modulos nuevos en orden de discovery. El orden completo previo
permanece en el launcher sin particion.

`discover(root)` devuelve dos listas ordenadas de IDs, con discovery estricto
del mismo proyecto inicializado y la misma configuracion. El modo CLI suite
produce el reporte ordinario para la particion con un campo `postinit_partition`
que contiene `shard` e `inventory`. Inventory son las dos listas de IDs
previstas desde el discovery completo anterior a la seleccion. Se requiere
coincidencia con expected_ids en la particion y reconciliacion de ejecutados
y omisiones aplicables. Ante fallo, emitir el veredicto real de la suite.
El reporte destino es nuevo y se escribe de forma exclusiva.

Para el pipeline, `run --repo-root DIR --shard 0|1 --receipt FILE` ejecuta el
fixture completo de init con su contencion y timeout exterior de 600 s. La
copia prepara sus mismos gates, elimina su oraculo externo para evitar
recursion y exporta el reporte tipado a la ruta privada nueva indicada por
`KDD_POSTINIT_RAW_REPORT`. El launcher consume las dos marcas antes de
ejecutar el discovery y los workers; estos no pueden heredarlas para su
propio trabajo. El comando requiere el exito del fixture y un reporte
valido segun el reconciliador completo del bundle aprobado, cargado antes de
ejecutar el fixture, incluidas las causas de omisiones,
antes de emitir el recibo compacto. El job
publica el recibo bajo el nombre definido en el [contrato de verificacion](postinit-windows-common-deadline.md).

## Invariants

- Los dos jobs inicializan copias independientes. No compartir directorios
  de trabajo, procesos, resultados ni artefactos de otra ejecucion.
- Ejecutar cada ID original en una unica particion, incluidos casos con SKIP
  previsto. Las omisiones de fixture conservan las reglas del reconciliador.
- Conservar el orden de lanzamiento declarado por particion, la contencion
  y los fallos por proceso. El modo por defecto sigue usando la suite completa.
- Conservar Ubuntu y los consumidores reutilizables en su perfil completo,
  asi como la base fijada de las dos suites generales.

## Examples

- A y D se asignan a 0, B y C a 1. El reporte de cada job enumera el mismo
  inventario completo, con sus propios ID ejecutados.
- Dos grupos asignan el mismo modulo. La CLI falla antes de ejecutar tests.
- El worker de la particion falla. El reporte conserva el error y el comando
  devuelve un resultado fallido.

## Do / Don't

Usar descubrimiento estricto y procesos reales. Los pesos de la corrida
anterior sirven para balancear nombres. La presencia de una entrada de
perfil nunca reemplaza casos descubiertos.

## Tests

Ejecutar ambos grupos en dos copias inicializadas sin Git y comprobar los
IDs individuales contra un control completo real. Los canarios ejecutados
acreditan la particion. Probar particion fallida, perfil duplicado y destino
previo. El control de discovery es una tercera copia fresca.

## Constraints

PARAR y reportar si falta aprobar el contrato y oraculo, cambia la cobertura
o se supera el [plazo comun](postinit-windows-common-deadline.md).
