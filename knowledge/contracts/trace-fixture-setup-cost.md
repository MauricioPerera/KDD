---
type: 'Task Contract'
title: 'Reducir procesos Git del fixture de trazabilidad'
description: 'Conservar clones reales e independientes sin lanzar Git para cada ajuste local.'
tags: ['ci', 'fixtures', 'git', 'performance']
task: trace-fixture-setup-cost
intent: 'Reducir el costo de preparacion del fixture de trazabilidad preservando sus controles.'
target: tests/test_traceability_model.py
signature: 'def prepare_project(root):'
test_command: 'python -m unittest tests.test_trace_fixture_setup_cost'
budget:
  cyclomatic_max: 40
  nesting_max: 8
tests: tests/test_trace_fixture_setup_cost.py
tests_sha256: 'c51c7856daf339e9f9d6f0c18f29ebda306429a1b71be8ccba1f92b1828d0b17'
touch_only: ['tests/test_traceability_model.py']
deps_allowed: ['stdlib', 'test_fixture_preparation', 'git']
forbids: ['network', 'llm']
---

## Intent
Reducir el coste repetido observado en la [remediacion](../audit-p1-p2-remediation.md)
sin disminuir la auditoria real de [trazabilidad](traceability-model.md).

## Interface
Conservar prepare_project, RepositoryFixture y todos sus llamadores y asserts.
Usar configuracion local equivalente para el repo base y cada clon Git real.

## Invariants
- Cada clon conserva su HEAD, ramas, objetos, estado de trabajo y configuracion
  independiente. La configuracion de un clon no modifica su fuente ni otros.
- El repo base y los clones aplican las mismas cuatro opciones locales actuales.
  Evitar subprocess Git para cada opcion; conservar el `git clone --shared` real.
- Respetar los limites fisicos del helper existente: config regular local con un
  enlace; rechazar alias y no tocar configuracion global. No usar shell ni red.
- Conservar todos los metodos, asserts y oraculos anteriores; mantener suites
  dobles, matriz, timeouts y test_command de init. No declarar ahorro de CI sin
  medicion comparable del post-init completo y del runner remoto.

## Examples
- Un clon nuevo usa un proceso Git para clone y cero para ajustes locales.
- Una mutacion de config y archivos en un clon no cambia fuente ni otro clon.

## Do / Don't
- DO contar subprocess reales y comprobar Git y trazabilidad sobre clones reales.
- DON'T usar mocks de Git, bajar cobertura, modificar limits o afirmar sandbox.

## Tests
`tests/test_trace_fixture_setup_cost.py` registra subprocess con audit hooks,
lee configuracion de Git, comprueba dos clones, historia y consulta de
trazabilidad real. El helper congelado se presenta para revision humana con
su sello actualizado antes de adoptarlo.

## Constraints
PARAR y reportar si se necesita otro archivo de produccion, runtime o proteccion.
La modificacion del fixture congelado exige otro baseline aprobado; no ampliar
el timeout ni convertir un fallo en exito.
