---
type: 'Task Contract'
title: 'Comillas portables en comandos del auditor de mutaciones'
description: 'Ejecutar el mismo oracle con argumentos entrecomillados en Windows y Ubuntu sin shell.'
tags: ['mutation', 'windows', 'integration']
task: mutation-command-quoting
intent: 'Evitar falsos fallos de controles por comillas literales en argv.'
target: scripts/mutation_audit.py
language: python
signature: 'def _command(value):'
test_command: 'python -m unittest tests/test_mutation_command_quoting.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
  lines_max: 35
  params_max: 2
tests: tests/test_mutation_command_quoting.py
tests_sha256: '4f3b1beedfd50d35a1c1864563ab0433b557bd54c440a3d5548ad5494d08c5c7'
touch_only: ['scripts/mutation_audit.py']
deps_allowed: ['stdlib', 'process_tree']
forbids: ['network', 'llm']
---
## Intent
Aplicar la [tokenizacion portable](../audit-mutation-approval-ci.md).
## Interface
Conservar argv y ejecucion sin shell. Eliminar comillas envolventes conforme al
runner actual de contratos; no alterar backslashes de rutas Windows.
## Invariants
Comillas validas no producen ImportError/not-found. Paths con espacios/Unicode,
argumentos, controles fallidos y mutantes supervivientes conservan su semantica.
## Examples
- python -m unittest "tests/test_app.py": mismas detecciones que sin comillas.
- ejecutable Python absoluto entrecomillado con espacios: oracle real ejecutado.
## Do / Don't
- DO comprobar procesos y salidas reales en ambos SO.
- DON'T usar shell=True o simular exit codes.
## Tests
El oraculo cubre equivalencia, espacios, CLI estricto y controles genuinos fallidos.
## Constraints
PARAR y reportar si requiere runtime, locks, workflows u oraculos previos no revisados.
