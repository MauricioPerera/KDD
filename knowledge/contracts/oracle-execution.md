---
type: 'Task Contract'
title: 'Comprobar la ejecucion del oraculo declarado'
description: 'Runners instrumentados para unittest y node:test rechazan omisiones y resultados vacios.'
tags: ['ccdd', 'verification', 'security']
task: oracle-execution
intent: 'Comprobar que el oraculo declarado ejecuta casos reales aprobados.'
target: scripts/oracle_execution.py
signature: 'def execute_oracle(metadata, repo_root, timeout=180) -> dict'
test_command: 'python -m unittest tests.test_oracle_execution tests.test_contract_timeouts tests.test_oracle_runtime_binding'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 65
  params_max: 5
tests: tests/test_oracle_execution.py
tests_sha256: 58310b12e05ea62c4dbcc78bb3127669aa5cf22d6de500bb37f7fecd5088125a
oracle_files: ['tests/test_oracle_execution.py', 'tests/test_contract_timeouts.py', 'tests/test_oracle_runtime_binding.py', 'tests/__init__.py']
touch_only: ['scripts/oracle_execution.py', 'scripts/unittest_oracle_runner.py', 'scripts/node_oracle_reporter.mjs', 'scripts/validate_test_commands.py', 'scripts/guard_pr_baseline.py', 'scripts/preflight.py']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
Vincular la invocacion y la evidencia al oraculo definido en [el inventario aprobado](./oracle-inventory.md), en vez de aceptar cualquier exit 0.

## Interface
`test_runner` selecciona `python-unittest` o `node-test`. Solo se admiten invocaciones explicitas de archivos/modulos de test inventariados; sin selectors ni opciones que omitan casos. `execute_oracle` devuelve el resultado, cantidad ejecutada y evidencia del runner. Los comandos historicos sin runner conservan su semantica limitada de exit code.

## Invariants
- La invocacion debe incluir `tests` y solo archivos inventariados.
- Un alias Python con version debe coincidir con el interprete instrumentado; la evidencia registra su argv real y version.
- Cero casos, skips/todos, salida temprana, fallo, timeout, runner desconocido o evidencia faltante bloquean.
- El stdout del test no se interpreta como atestacion del runner.
- Un archivo Node que termina sin registrar casos no cuenta como prueba.

## Constraints
PARAR y reportar si el comando requiere un adapter no disponible. Los runtimes, runners y oraculos aprobados son confiables; no hay sandbox contra codigo arbitrario hostil. La cantidad no demuestra fuerza semantica ni independencia humana: ver [quality-approval](../quality-approval.md).

## Examples
- `python noop.py` con `tests: oracle.py` no demuestra ejecucion.
- `node --test oracle.mjs` sin casos registrados es FAIL aunque Node salga con 0.

## Do / Don't
- DO: capturar evidencia del runner y rechazar casos omitidos.
- DON'T: contar mensajes TAP falsos o prose PASS como pruebas reales.

## Tests
El oraculo cubre Python y Node, targets incorrectos, omision del archivo, selectors, cero casos, skips/todos, salida temprana, stdout falso, timeout e integracion con comandos de contratos.
