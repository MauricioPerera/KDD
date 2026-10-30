---
type: 'Task Contract'
title: 'Conservar el interprete activo al medir mutaciones'
description: 'Evitar que un alias Python cambie de entorno y rompa los controles originales.'
tags: ['mutation', 'runtime', 'quality']
task: mutation-python-runtime
intent: 'Vincular los alias Python genericos al interprete activo del auditor.'
target: scripts/mutation_audit.py
language: python
signature: 'def _command(value):'
test_command: 'python -m unittest tests/test_mutation_python_runtime.py'
test_runner: python-unittest
oracle_files: ['tests/test_mutation_python_runtime.py']
budget:
  cyclomatic_max: 18
  nesting_max: 5
  lines_max: 220
  params_max: 5
tests: tests/test_mutation_python_runtime.py
tests_sha256: 4bd938ca5c29f35310f43ce0794a1a80c26b77f82bae8d40bcd24ac17cb1ba05
touch_only: ['scripts/mutation_audit.py']
deps_allowed: ['stdlib', 'process_tree']
forbids: ['network', 'llm']
---

## Intent
Conservar la identidad del runtime en los [controles de mutacion](../audit-remediation-approval-mutation-board.md).

## Interface
Mantener _command, audit_contract y CLI. Normalizar python, python3 y python.exe a sys.executable; los ejecutables especificos y los argumentos conservan su significado.

## Invariants
- Un alias generico no escapa del venv activo aunque PATH prefiera otro Python.
- Un ejecutable absoluto explicito no se sustituye.
- Se conservan controles original/copy, cero detecciones ante controles rotos y la contencion existente.
- Los oraculos anteriores permanecen congelados.

## Examples
- Auditor en venv con python global primero en PATH: los controles usan el venv.
- Un ejecutable absoluto entrecomillado: se conserva su seleccion explicita.

## Do / Don't
DO: comprobar la identidad en procesos reales. DON'T: alterar paquetes globales, modificar process_tree o contar ImportError como mutacion detectada.

## Tests
El oraculo sellado cubre aliases, ejecutable explicito y un venv real que detecta tres mutantes.

## Constraints
PARAR y reportar si hace falta cambiar locks, contencion o un oraculo anterior. La instalacion de dependencias de pruebas se prepara fuera del checkout.
