---
type: 'Task Contract'
title: 'Preparacion compartida del fixture de perimetro'
description: 'Reutilizar una base inmutable y clonar repositorios reales por caso sin perder aislamiento.'
tags: ['ci', 'fixtures', 'git', 'performance']
task: perimeter-fixture-snapshot
intent: 'Reducir la creacion repetida del fixture de perimetro sin cambiar sus oraculos.'
target: tests/test_task_finish_perimeter.py
signature: 'class PerimeterProject(TaskProject):'
test_command: 'python -m unittest tests.test_perimeter_fixture_snapshot'
budget:
  cyclomatic_max: 40
  nesting_max: 8
tests: tests/test_perimeter_fixture_snapshot.py
tests_sha256: '1b47fb57889b9c17cfc6afb04b445e7e84d428bcfd91430ecc2051b37dda968c'
touch_only: ['tests/test_task_finish_perimeter.py']
deps_allowed: ['stdlib', 'test_generated_task_evidence', 'test_fixture_preparation', 'git']
forbids: ['network', 'llm']
---

## Intent
Reducir el coste repetido de [perimetro](task-finish-perimeter.md), su historial
[historico](task-perimeter-history.md) y [controles](task-operation-controls.md).

## Interface
Conservar `PerimeterProject(root)`, sus metodos y la API de sus fixtures.
Preparar una base Git inmutable por proceso y clonar un repositorio real por caso.

## Invariants
- En rutas nuevas o vacias, preparar una sola base sintetica por clase concreta
  y proceso y construir un clon independiente por instancia. Crear padres
  faltantes. En directorios no vacios, conservar la inicializacion anterior y
  sus archivos existentes. La base permanece disponible para sus clones.
- Conservar configuracion local, contenido de contrato/oraculo, marcas,
  historial y ramas. Modificar o cerrar una tarea en un clon no altera otro.
- Preservar exactamente los metodos y aserciones de oraculos previos, flags de
  mantenimiento, dos pasadas, matriz y timeouts. Sin fixtures compartidos entre
  procesos ni aumento de privilegios o acceso externo.
- Ningun resultado de prueba se reutiliza: cada caso ejecuta sus propios Git,
  oraculos y operaciones. No afirmar mejora de CI sin mediciones comparables.

## Examples
- Dos instancias usan una preparacion y dos clones Git reales.
- Cambiar un clon no altera el otro; este puede completar tarea y evidencia.

## Do / Don't
- DO comprobar procesos, Git real, marcas y tareas en rutas temporales aisladas.
- DON'T compartir arboles modificables ni eliminar o simular aserciones previas.

## Tests
`tests/test_perimeter_fixture_snapshot.py` comprueba subprocess, configuracion,
dos clones y ciclo de tarea real. Se conserva el cuerpo de todos los metodos de
prueba sellados de perimetro y sus consumidores de historial y operaciones.

## Constraints
PARAR y reportar si se requiere cambiar produccion, runtime o protecciones.
El cambio del fixture congelado exige baseline humano antes de adoptarlo.
