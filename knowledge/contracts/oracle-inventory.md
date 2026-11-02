---
type: 'Task Contract'
title: 'Proteger el inventario aprobado del oraculo'
description: 'Extiende la comparacion de baseline al conjunto declarado de pruebas y archivos de soporte.'
tags: ['ccdd', 'verification', 'security']
task: oracle-inventory
intent: 'Proteger todos los archivos declarados del oraculo contra una referencia aprobada.'
target: scripts/oracle_inventory.py
signature: 'def inventory_paths(metadata, required=False) -> list'
test_command: 'python -m unittest tests.test_oracle_inventory tests.test_inventory_admission tests.test_binary_oracle_inventory'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 60
  params_max: 4
tests: tests/test_oracle_inventory.py
tests_sha256: 9c92dbcba88d7475b1433786e9e1709f4dd052731c6c1c7ec4ff2813abe9d80c
oracle_files: ['tests/test_oracle_inventory.py', 'tests/test_inventory_admission.py', 'tests/test_binary_oracle_inventory.py', 'tests/test_contract_acceptance.py', 'tests/__init__.py']
touch_only: ['scripts/oracle_inventory.py', 'scripts/validate_baseline.py', 'scripts/guard_pr_baseline.py', 'scripts/validate_contracts.py']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
Cerrar la brecha de helpers modificables descrita en [las garantias](../verification-guarantees.md) sin convertir la compatibilidad historica en aprobacion de aceptacion.

## Interface
`oracle_files` es una lista exacta de rutas relativas, sin duplicados ni patrones, que incluye `tests`. El inventario se lee del contrato aprobado; nunca del candidato para decidir que proteger. `required=True` rechaza contratos sin inventario.

## Invariants
- El baseline local y el gate confiable de PR comparan cada archivo del inventario aprobado.
- Helpers, fixtures y configuracion declarados no pueden neutralizarse, eliminarse o retirarse del inventario del candidato sin findings.
- El perfil historico sigue comparando `tests` cuando no existe inventario; no promete aceptacion completa.
- Rutas ambiguas, escapes, duplicados y symlinks no se aceptan como inventario.

## Constraints
PARAR y reportar si falta el commit aprobado o un archivo inventariado en ese commit. La completitud semantica del inventario y la confianza en runner/revisor son supuestos externos: ver [quality-approval](../quality-approval.md). El helper puro no usa red ni procesos; las comparaciones Git existentes conservan su transporte.

## Examples
- Un target incorrecto y un helper neutralizado mantienen el test principal intacto: el baseline debe detectar el helper.
- Cambiar unicamente implementacion conserva la integridad del inventario, aunque no demuestra correccion.

## Do / Don't
- DO: leer la lista aprobada y comprobar cada archivo declarado.
- DON'T: inferir que una lista aprobada descubre automaticamente toda dependencia dinamica.

## Tests
El oraculo congelado cubre helpers neutralizados, cambios de fixture/configuracion, eliminacion, resello del contrato, comparacion por objetos Git, rutas peligrosas y compatibilidad historica explicita.
