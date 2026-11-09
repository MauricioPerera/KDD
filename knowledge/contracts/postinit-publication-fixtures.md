---
type: 'Task Contract'
title: 'Preparacion acotada de diarios para pruebas de publicacion'
description: 'Reutilizar la preparacion de dos fixtures reales de Git con copias privadas por caso.'
tags: ['ci', 'windows', 'git', 'performance']
task: postinit-publication-fixtures
intent: 'Reducir las operaciones Git de preparacion del post-init.'
target: tests/test_task_git.py
signature: 'def independent_copy(self):'
test_command: 'python -m unittest tests.test_postinit_publication_fixtures'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_postinit_publication_fixtures.py
tests_sha256: '7766876bdec62437223e692d97d07d6b188b4f6eb82ee70507e10590f4150133'
oracle_files: ['tests/test_postinit_publication_fixtures.py', 'tests/test_fixture_preparation.py']
touch_only: ['tests/test_task_git.py', 'tests/test_task_publication.py', 'tests/test_task_import_ancestry.py', 'tools/ci/postinit-module-order.json']
deps_allowed: ['stdlib', 'test_fixture_preparation', 'task_git', 'task_model']
forbids: ['network', 'llm']
---

## Intent
Reducir la preparacion repetida antes de las comprobaciones reales de
[publicacion](task-publication.md) y [ascendencia](task-import-ancestry.md).
Mantener el [protocolo de tres mediciones](../postinit-proof-cost.md).

## Interface
La preparacion de cada clase usa Git real una vez por invocacion. La de
publicacion termina con la tarea iniciada y conserva el commit de inicio.
La de ascendencia termina en la rama feature con el fork y el nodo originales.
Cada caso recibe un directorio y repositorio fisicos independientes.
Actualizar las prioridades de Windows segun los perfiles registrados con el
[contrato de orden vigente](postinit-module-order.md).

## Invariants
- Conservar historial, ramas locales, HEAD, indice, configuracion, objetos,
  bytes del producto y los OID que necesita cada prueba. Sin hardlinks,
  alternates ni repositorio de objetos comun. El directorio de origen es
  exclusivo de la clase y solo contiene preparacion.
- Cada caso conserva su merge, mutacion, validacion o cierre real. Cada cierre
  ejecuta el oraculo y produce evidencia en su copia. El repositorio base no
  contiene cierre ni resultado de pruebas. Los tests independientes de
  create, ready y start siguen ejecutando esas operaciones.
- Conservar literalmente los IDs y las aserciones, incluidos los controles
  de squash, historial incompleto, alteraciones intermedias y conflictos.
  Mantener los 2.205 IDs previos, las omisiones aplicables y ambas pasadas
  generales en Ubuntu y Windows. El perfil solo ordena todos los jobs existentes.
- Registrar la limpieza de cada directorio antes de preparar o copiar. Un
  error de copia o Git impide usar la preparacion parcial. Una invocacion
  posterior prepara un estado nuevo. Mantener timeout 600 s, workers y runtime.

## Examples
- Dos casos de publicacion comparten la preparacion del inicio. Cada uno
  audita su propio merge sobre un repositorio de objetos privado.
- Un caso de ascendencia altera el indice y crea un commit. La base y la
  otra copia conservan exactamente sus refs y su indice.

## Do / Don't
- DO contar los arranques de Git con Trace2 y comparar los inventarios reales.
- DON'T compartir un resultado de validacion o alterar las aserciones congeladas.

## Tests
Las integraciones nuevas cuentan los procesos de preparacion y verifican
estado, objetos sin enlaces duros y limpieza ante fallos reales de Git o copia. Los casos de publicacion y
ascendencia existentes comprueban el comportamiento de cada escenario.

## Constraints
PARAR y reportar si se requiere modificar otro oraculo, runtime, workflow o
proteccion sin revision expresa. El baseline incluye las propuestas y sellos
de los fixtures congelados. El cierre requiere tres CI completos consecutivos
del mismo SHA en main, cada post-init Windows estrictamente menor de 480 s.
