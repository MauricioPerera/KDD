---
type: 'Task Contract'
title: 'Exigir evidencia por obligacion de aceptacion'
description: 'Ejecuta una politica aprobada con inventario, runners y matriz bloqueante por contrato.'
tags: ['ccdd', 'verification', 'quality']
task: contract-acceptance
intent: 'Bloquear la aceptacion cuando falte evidencia ejecutada de una obligacion requerida.'
target: scripts/verify_acceptance.py
signature: 'def verify_acceptance(repo_root, policy_path, approved_ref) -> dict'
test_command: 'python -m unittest tests.test_contract_acceptance tests.test_acceptance_integration tests.test_acceptance_missing_matrix tests.test_acceptance_workflow tests.test_quality_budget_review tests.test_methodology_remote_integration'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 80
  params_max: 6
tests: tests/test_contract_acceptance.py
tests_sha256: 527490867a309f5ac4108b4ac7f1f26bb8c45f36a7378a907fd29a6818d00295
oracle_files: ['tests/test_contract_acceptance.py', 'tests/test_acceptance_integration.py', 'tests/test_acceptance_missing_matrix.py', 'tests/test_acceptance_workflow.py', 'tests/test_quality_budget_review.py', 'tests/fixtures/methodology-budget-baseline.json', 'scripts/validate_budgets.py', 'knowledge/contracts/verify-quality.md', 'knowledge/contracts/run-profile.md', 'knowledge/contracts/test-command-gate.md', 'tests/test_methodology_remote_integration.py', 'tests/test_ci_trusted_execution.py', 'tests/__init__.py']
touch_only: ['scripts/verify_acceptance.py', 'scripts/verify_quality.py', 'scripts/run_profile.py', 'scripts/guard_pr_baseline.py', '.github/workflows/validate.yml', 'scripts/trusted_ci.py', 'scripts/validate_test_commands.py']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
Hacer operativa la separacion entre validacion estructural, pruebas aprobadas y aceptacion descrita en [quality-approval](../quality-approval.md).

## Interface
La politica JSON version 1 declara contratos, checks por obligacion, archivos de implementacion y archivos del PM. Se lee del SHA completo aprobado. Cada contrato requiere [inventario](./oracle-inventory.md) y [runner](./oracle-execution.md). La matriz incluye integridad, ejecucion, perimetro, firma, dependencias, budget, prohibiciones e invariantes; las obligaciones adicionales del contrato tambien requieren check.

## Invariants
- Ausencia, fallo, omission, timeout o instrumento no soportado nunca producen aceptacion aprobada.
- Los oraculos de cada check pertenecen al inventario protegido y ejecutan casos reales mediante un runner reconocido.
- El diff real staged/unstaged/committed/untracked no ignorado queda dentro del perimetro aprobado.
- Evidencia ligada a SHA aprobado, contrato, inventario y snapshot de implementacion; se comprueba integridad antes y despues de cada check.
- Cada check corre dos veces como comprobacion basica de repetibilidad, sin afirmar ausencia de flaky.

## Constraints
PARAR y reportar si no existe aprobacion externa del SHA o si falta un check requerido. Los nombres de checks no demuestran su fuerza semantica: el revisor aprueba que cada oraculo cubra su obligacion y prueba escenarios adversariales. No se autentica al revisor ni se proporciona sandbox.

## Examples
- Todos los tests funcionales pasan pero falta budget: la matriz bloquea aceptacion.
- Un check de dependencias termina con exit 0 y cero casos: no cuenta como evidencia.

## Do / Don't
- DO: entregar matriz completa con instrumentos y hashes reproducibles.
- DON'T: usar el perfil historico o seleccionar HEAD para suplir una aprobacion externa.

## Tests
El oraculo cubre matriz completa, obligaciones ausentes, implementacion incorrecta, helper neutralizado, noop, cero casos, runners/inventarios ausentes, checks no inventariados, perimetro real, politica modificada, timeout y modificaciones durante verificacion.
