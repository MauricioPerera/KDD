---
type: 'Task Contract'
title: 'Conservar el runtime Python de los comandos de contrato'
description: 'Evitar que un comando Python historico ignore el venv activo en Windows.'
tags: ['runtime', 'ci', 'quality']
task: contract-python-runtime
intent: 'Vincular los alias Python genericos de contratos al interprete activo.'
target: scripts/validate_test_commands.py
language: python
signature: 'def run_test_command(cmd, cwd, timeout, capture=False, *, trusted_bundle=None):'
test_command: 'python -m unittest tests/test_contract_python_runtime.py'
test_runner: python-unittest
oracle_files: ['tests/test_contract_python_runtime.py']
budget:
  cyclomatic_max: 20
  nesting_max: 6
  lines_max: 220
  params_max: 8
tests: tests/test_contract_python_runtime.py
tests_sha256: 3e2e5e90ec506c5644f76306b2b125ca4c9c0fb7ebbcdbe3fa0f819e1dd96309
touch_only: ['scripts/validate_test_commands.py']
deps_allowed: ['stdlib', 'validate_contracts', 'process_tree', 'oracle_execution']
forbids: ['network', 'llm']
---

## Intent
Preservar el runtime de [validacion](../validacion.md) sin modificar la contencion.

## Interface
Conservar run_test_command y su resultado, captura, timeout, deduplicacion y argumentos. Los alias python, python3 y python.exe usan sys.executable; los ejecutables especificos permanecen exactos.

## Invariants
- La ejecucion real de un alias permanece en el venv activo aunque PATH seleccione otro Python.
- No se modifica un ejecutable absoluto ni un alias de version especifica.
- No se usa shell ni se modifican paquetes globales, process_tree o tests anteriores.

## Examples
- python -c imprime el prefix del venv activo.
- Un Python absoluto conserva su seleccion explicita.

## Do / Don't
DO: medir el proceso hijo real. DON'T: simular exit codes o degradar el runner instrumentado.

## Tests
El oraculo sellado comprueba alias, ejecutable explicito y prefix real de un venv.

## Constraints
PARAR y reportar si se requiere cambiar contencion, locks u oraculos previos.
