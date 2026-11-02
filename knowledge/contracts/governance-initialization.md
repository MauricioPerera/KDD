---
type: 'Task Contract'
title: 'Inicializacion compatible con el objetivo de gobierno'
description: 'Retirar solamente la spec de gobierno propia de KDD al instanciar otro proyecto, conservando el inventario exacto y su precheck.'
tags: ['initialization', 'governance', 'regression']
task: governance-initialization
intent: 'Extender el inventario explicito para la spec abierta de gobierno.'
target: scripts/init_project.py
signature: 'def init_project(repo_dir, apply, name, repository=None) -> dict:'
test_command: 'python -m unittest tests.test_governance_initialization'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_governance_initialization.py
tests_sha256: '583429434acc55d21f24dd628deec5ba763c7a6e1c1d50bf31a813169419dfba'
touch_only: ['scripts/init_project.py']
deps_allowed: ['stdlib', 'bootstrap_transaction']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Resolver el acoplamiento descubierto en CI segun la
[extension de inventario](../governance-initialization.md), conservando el
[inicializador](init-project.md) y el [objetivo](../kdd-governance-closure.md).

## Interface

Conservar API, CLI, dry-run y resultado del inicializador. Solo agregar la
ruta exacta aprobada al inventario; sin descubrimiento de permisos por glob.

## Invariants

- Dry-run incluye una sola vez la spec de gobierno y no modifica bytes.
- Apply elimina esa spec propia de KDD, conservando specs/reportes propios.
- Si falta la ruta nueva o cualquier entrada previa, abortar antes de borrar.
- Conservar los 33 pares historicos, completion-legacy y todos sus digests.
- Mantener todas las comprobaciones, transacciones y presupuestos existentes.

## Examples

- Copia integra -> plan con CONTRACT-34 y apply sin esa spec de KDD.
- Copia con CONTRACT-999 propio -> archivo conservado byte por byte.
- Falta CONTRACT-34 -> ValueError antes de escribir o eliminar archivos.

## Do / Don't

- DO mantener el inventario explicito y probar copias temporales reales.
- DON'T eliminar specs por patron, crear cierres historicos o editar otro gate.

## Tests

Oraculo nuevo en tests/test_governance_initialization.py. El cambio revisable
de tests/test_init_project.py solo actualiza el conteo de specs a 34 y agrega
pertenencia exacta; su contrato conserva el sello nuevo y todas las demas pruebas.
Tras implementar, ejecutar ambos comandos y repetir el CI completo dual-OS 2x.

## Constraints

PARAR y reportar si hace falta otra fuente, cambiar otro oraculo, aumentar un
presupuesto o modificar workflows/protecciones. No implementar esta extension
antes de que una persona apruebe el baseline nuevo con sus diferencias exactas.
