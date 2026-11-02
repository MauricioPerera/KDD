---
type: 'Task Contract'
title: 'Diagnosticar la ejecucion de validaciones'
description: 'Mide comandos por contrato, alinea el timeout global con los individuales y prepara Git nativo en Windows.'
tags: ['ccdd', 'infra', 'dx']
task: validation-diagnostics
intent: 'Hacer verificable la ejecucion local de los comandos de contratos.'
target: scripts/validate_test_commands.py
signature: 'def run_all(contracts_dir, repo_root, timeout=180) -> list'
test_command: 'python -m unittest tests/test_validation_diagnostics.py'
budget:
  cyclomatic_max: 18
  nesting_max: 4
tests: tests/test_validation_diagnostics.py
tests_sha256: 9d659dc54a27d199daa8cb38819df3788ff52d54e66e8bb9b1d0aced011b23f1
touch_only: ['scripts/validate_test_commands.py', 'scripts/preflight.py', 'scripts/validation_runtime.py', 'scripts/run_profile.py', '.github/workflows/validate.yml', 'knowledge/validacion.md', 'knowledge/verification-guarantees.md', 'README.md']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
Completar el diagnostico local de [validacion](../validacion.md) sin omitir contratos ni debilitar los limites individuales.

## Interface
Agregar duration_seconds por comando y --timings-json para un manifiesto sin stdout/stderr. Ofrecer python scripts/validation_runtime.py suite, preflight o contracts con Git nativo en Windows.

## Invariants
- Un timeout nunca se suma como PASS.
- El limite global permite todos los limites individuales mas margen de arranque.
- La preparacion de PATH no modifica la configuracion global del equipo.
- El lanzador conserva el exit code del comando ejecutado.

## Examples
- Tres comandos con timeout 180 -> timeout global mayor que 540.
- Un comando fallido -> FAIL en el manifiesto y exit code 1.
- Git MSYS primero en Windows -> Git nativo primero en el entorno del subproceso cuando esta instalado.

## Do / Don't
- DO conservar las pruebas originales y sus sellos.
- DON'T desactivar comprobaciones TLS ni saltar comandos para ahorrar tiempo.

## Tests
El oraculo sellado comprueba tiempos, veredictos, limite global y propagacion del entorno/exit code.

## Constraints
- PARAR y reportar si resolver un fallo requiere cambiar un oraculo historico.
- La modificacion del workflow queda local y revisable; no publicar.
