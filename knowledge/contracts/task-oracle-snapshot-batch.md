---
type: 'Task Contract'
title: 'Lectura por lotes del inventario de oraculos de tareas Git'
description: 'Reduce lanzamientos de Git por comprobacion sin reutilizar lecturas entre etapas.'
tags: ['git', 'performance', 'tasks', 'oracle']
task: task-oracle-snapshot-batch
intent: 'Leer con menor coste el contrato y su inventario durante cada comprobacion Git.'
target: scripts/task_git.py
signature: 'def contract_metadata(root, data, revision, *, committed_only=False):'
test_command: 'python -m unittest tests.test_task_oracle_snapshot_batch'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 160
  params_max: 5
tests: tests/test_task_oracle_snapshot_batch.py
tests_sha256: 'e6d24fad53292ff2a2539c4e8b91a77bfb4a56c24c48f7e3e44a2762d0e40867'
oracle_files: ['tests/test_task_oracle_snapshot_batch.py', 'tests/test_git_task_multi_oracle.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'scripts/trusted_ci.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'git', 'oracle_inventory']
forbids: ['network', 'llm']
---

## Intent

Reducir procesos Git observados en el modulo de [oraculos multiarchivo](git-task-multi-oracle.md).
Las lecturas agrupadas pertenecen a una sola comprobacion. Las comprobaciones
antes y despues del runner siguen leyendo sus respectivos objetos y archivos.

## Interface

Para una comprobacion con dos commits distintos y un inventario corto, leer
los modos y los cuerpos del contrato y sus oraculos con un solo proceso Git
de lectura de inventario cuando Git admite `cat-file --batch-command` con
`%(objectmode)`. La ruta portable de Git conserva dos listados de modos y un
lote de cuerpos para todos los OID; la deteccion de capacidad puede agregar
un proceso. No se cuentan las comprobaciones independientes de ascendencia,
rutas generales ni atributos aprobados en este presupuesto.
La lectura preliminar del contrato para descubrir el inventario usa el
objeto aprobado sin reemplazos y se coteja con el contrato del lote.
Un reemplazo no puede desactivar el inventario. En el escenario de prueba completo
el limite incluye todas las llamadas Git: 25 con soporte de modo, 27 en la
ruta portable ya seleccionada y 28 si primero se detecta la capacidad.

## Invariants

- Resolver las mismas identidades y comprobar rutas exactas, modos regulares y
  blobs de ambos commits, aunque los bytes coincidan. Rechazar sin acreditar
  nada si una ruta es un enlace, directorio, gitlink, o falta un objeto.
- No aplicar reemplazos Git a modos o cuerpos del inventario. La prueba de
  atributos y el sello canonico siguen vigentes. Conservar bytes binarios,
  normalizacion de texto, lado local y diagnosticos de rechazo.
- Leer de nuevo al cambiar de etapa. El auditor historico no ejecuta oraculos.
  Reutilizar lectores y detectores de capacidad existentes cuando preserven
  estos limites; no mezclar una lectura general con otra sin reemplazos.
- Mantener Ubuntu, Windows, ambas pasadas, cobertura inicial y el limite
  oficial de 600 segundos de `init-project`.

## Examples

- Dos commits diferentes comparten todo el inventario y se verifican.
- El ultimo oraculo conserva el OID pero cambia a modo enlace, y falla.

## Do / Don't

Usar Git real y leer objetos por longitud. Conservar la ruta portable para
Git sin el formato de modo, incluidos los diagnosticos de formato
`unknown format element: objectmode` y `bad cat-file format: %(objectmode)`.
Fallar ante una respuesta dañada u otros errores Git.

## Tests

Ejecutar la comprobacion de tareas en repositorios Git reales con Trace2,
un recurso binario, un camino no regular y un reemplazo que oculta cambios.

## Constraints

PARAR y reportar si se necesita cambiar workflows, runtime fijado, timeout
o protecciones. La reduccion de procesos se comprueba por separado del tiempo
del post-init completo.
