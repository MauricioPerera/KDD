---
type: 'Task Contract'
title: 'Identidad de aceptacion'
description: 'Vincular ambas pasadas de aceptacion al commit y a los mismos casos.'
tags: ['audit', 'acceptance']
task: acceptance-identity
intent: "Vincular la aceptacion al OID de commit y a los casos observados."
target: scripts/verify_acceptance.py
signature: "def verify_acceptance(repo_root, policy_path, approved_ref)"
test_command: "python -m unittest tests.test_acceptance_identity"
test_runner: python-unittest
oracle_files: ['tests/test_acceptance_identity.py', 'tests/test_contract_acceptance.py', 'tests/__init__.py', 'knowledge/contracts/oracle-inventory.md']
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 80
  params_max: 6
tests: "tests/test_acceptance_identity.py"
tests_sha256: '3a5ac2ccbd3d5dd5c585826cc1d03a98567a1f5b457d2c9656864b75e5a70437'
touch_only: ['scripts/verify_acceptance.py', 'scripts/oracle_execution.py', 'scripts/node_oracle_reporter.mjs']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
P2-17 y P2-18 de [aceptacion](../acceptance.md).

## Interface
OID de commit completo en formato nativo. Guardar ambos recibos por obligacion.

## Invariants
Cotejar los IDs vinculados completos y el archivo, independiente del orden.
Node registra [archivo seleccionado, camino] en JSON. Cada nodo del camino
conserva archivo de registro, linea, columna y nombre, desde la raiz hasta
el caso. Un ID ambiguo impide aprobar.
Activar IDs Node en aceptacion. El recibo de adopcion sigue siendo Python.

## Examples
- Dos hojas del mismo helper bajo padres distintos: IDs distintos.
- Mover una hoja entre padres cambia el inventario.

## Do / Don't
- DO: conservar los recibos del runner.
- DON'T: usar el OID de una etiqueta anotada.

## Tests
CLI, Git y runners reales.

## Constraints
PARAR y reportar si falta la aprobacion humana.
