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
tests_sha256: '4ab8b955ea4a02c9c986d2e221c0dc32ae39c10d5da679b9bb43ca76e319bc85'
touch_only: ['scripts/verify_acceptance.py', 'scripts/oracle_execution.py', 'scripts/node_oracle_reporter.mjs']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
P2-17 y P2-18 de [aceptacion](../acceptance.md).

## Interface
La referencia identifica un commit. Ambas pasadas guardan los IDs de cada obligacion.

## Invariants
Cotejar identidad y archivo seleccionado, independiente del orden.
Node registra [archivo seleccionado, camino] en JSON. Cada nodo del camino
conserva archivo de registro, linea, columna y nombre, desde la raiz hasta
el caso. Un ID ambiguo impide aprobar. El modo de conteo conserva su recibo.

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
