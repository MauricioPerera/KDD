---
type: 'Task Contract'
title: 'Aislar el paquete del fixture de trazabilidad'
description: 'Ejecutar el proyecto Git de prueba sin importar un paquete src ajeno.'
tags: ['traceability', 'tests', 'isolation']
task: traceability-fixture-package
intent: 'Conservar la fase roja y el cierre real ante un paquete src externo.'
target: tests/test_traceability_model.py
language: python
signature: 'def prepare_project(root):'
test_command: 'python -m unittest tests/test_traceability_fixture_isolation.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 200
  params_max: 5
tests: tests/test_traceability_fixture_isolation.py
tests_sha256: '0aa02f96f74ebbdbc989ee722821dde07c8c6582def3933b8b7cf915c4d55262'
touch_only: ['tests/test_traceability_model.py']
deps_allowed: ['stdlib', 'git']
forbids: ['llm', 'network']
---

## Intent
El fixture compartido del [modelo](traceability-model.md) no debe depender de
paquetes instalados en el host que tengan el mismo nombre que el producto.

## Interface
Crear un paquete src explicito en el proyecto temporal antes del baseline y
mantener el flujo de Git, fase roja, tarea cerrada y trazabilidad real.

## Invariants
Conservar metodos, aserciones, checks y oraculos existentes. No cambiar la
semantica del producto ni ocultar un error de importacion como fase roja.

## Examples
- Un src externo en PYTHONPATH no sustituye src.value del proyecto temporal.
- El stub falla antes de implementar y la tarea cerrada se verifica de verdad.

## Do / Don't
- DO: usar Git, Python y un paquete competidor real.
- DON'T: alterar paquetes instalados ni depender de su ausencia.

## Tests
El oraculo crea un paquete competidor, inicializa la tarea y consulta su evidencia.

## Constraints
El fixture congelado y su sello necesitan baseline revisado antes de usarse.
Conservar cobertura, Ubuntu/Windows y dos pasadas. Sin cambios de proteccion.
PARAR y reportar si se necesita alterar otro oraculo sin revision explicita.
