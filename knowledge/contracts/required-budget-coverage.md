---
type: 'Task Contract'
title: 'Medicion requerida de budgets con cobertura real'
description: 'Distinguir medidas Python efectivas de entradas omitidas o sin soporte.'
tags: ['governance', 'restrictions', 'quality']
task: required-budget-coverage
intent: 'Distinguir medidas Python efectivas de entradas omitidas o sin soporte.'
target: scripts/validate_budgets.py
signature: 'def measure_required(contracts_dir, repo_root, contract_name=None):'
test_command: 'python -m unittest tests.test_required_budget_coverage'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 180
  params_max: 3
tests: tests/test_required_budget_coverage.py
tests_sha256: 'd0a1dacce5da3eadc157dbfd667b07c5f3f2c046ca55a2dbe80a5e14d33998a4'
touch_only: ['scripts/validate_budgets.py']
deps_allowed: ['stdlib', 'validate_contracts']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Aplicar los [controles requeridos](../required-controls.md), conservando la
[aprobacion](../quality-approval.md), la [garantia de oraculos](../oracle-assurance.md)
y el [objetivo](../kdd-governance-closure.md).

## Interface

Conservar validate_directory y CLI anteriores. Agregar measure_required de
solo lectura y modo --required --json, con reporte canonico y exit no cero
si hay exceso, cero cobertura, falta de input o ausencia de soporte.

## Invariants

- Mantener las omisiones del API legacy; no presentarlas como cobertura requerida.
- Selector sin coincidencias y cero funciones medidas -> BUDGET_COVERAGE.
- Target ausente/no regular -> BUDGET_TARGET. Lenguaje o metrica sin soporte
  -> BUDGET_UNSUPPORTED; parseo fallido -> BUDGET_PARSE, nunca omitir como PASS.
- Medir con los algoritmos existentes. No subir limites ni ignorar keys desconocidas.
- Reportar schema_version, status, contracts_checked, functions_measured y
  measurements: metodo, lenguaje, scope, target, hash, limites y cada funcion/metrica.
- El hash del target usa SHA256 con LF normalizado, como la evidencia de tareas;
  declarar esa normalizacion. Un exceso conserva la medida que lo demuestra.
- No ejecutar producto ni instalar herramientas. AST Python no demuestra sandbox.

## Examples

- Un target Python valido -> una funcion medida, con hash, metodo y limites.
- Selector ausente, TypeScript o memory_max no soportados -> rechazo explicito.
- Complejidad dos frente a limite uno -> FAIL con ambas cifras.

## Do / Don't

- DO conservar entradas aprobadas, limites y evidencia de cobertura.
- DON'T convertir omision, fallo o falta de soporte en una garantia positiva.

## Tests

Nuevo tests/test_required_budget_coverage.py con procesos reales y temporales.
Los cuatro casos anteriores de test_validate_budgets siguen intactos y deben pasar.

## Constraints

PARAR y reportar si hace falta otra fuente, cambiar un oraculo anterior, elevar
budgets o modificar workflows. No implementar antes del baseline humano ni del
CI dual-OS 2x de KG-3. Conservar scope y algoritmos de las metricas existentes.
