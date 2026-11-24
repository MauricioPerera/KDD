---
type: 'Task Contract'
title: 'Entradas de CLI de validacion'
description: 'Rechazar opciones incompletas o invalidas y configuraciones de mensajes mal tipadas.'
tags: ['audit', 'quality']
task: validator-cli-inputs
intent: "Rechazar entradas ambiguas en las CLI de validacion."
target: scripts/validate_perimeter.py
signature: "def main(argv)"
test_command: "python -m unittest tests.test_validator_cli_inputs"
test_runner: python-unittest
oracle_files: ['tests/test_validator_cli_inputs.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: "tests/test_validator_cli_inputs.py"
tests_sha256: '6f528da455862e1e3d8bc437d8265cd331f54ca71a2faaf6e029a58f52ce8450'
touch_only: ['scripts/validate_perimeter.py', 'scripts/validate_contracts.py', 'scripts/validate_commit_message.py']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
P2-02, P2-03 y P3-08.

## Interface
[Perimetro](perimeter-gate.md) identifica opciones mal escritas.
Contratos identifica --hash o --repo-root con valor ausente, vacio u otra opcion.
[Mensajes](commit-message-gate.md) requiere types como lista de cadenas.
Cada error devuelve 1. La configuracion invalida emite CONFIG_INVALID.

## Invariants
Preservar stdin, --changed, hash y TYPE_UNKNOWN.

## Examples
- --repo-root sin valor: error, sin validacion.
- types con un entero: CONFIG_INVALID.

## Do / Don't
- DO: diagnosticar antes de validar.
- DON'T: cambiar las APIs.

## Tests
CLI con argumentos, archivos y stdin.

## Constraints
PARAR y reportar si falta el baseline humano.
