---
type: 'Task Contract'
title: 'Referencia aprobada del oraculo'
description: 'Detectar cambios de contrato y test respecto de un commit aprobado.'
tags: ['ccdd', 'security']
task: validate-baseline
intent: 'Comparar contrato y oraculo contra una referencia independiente.'
target: scripts/validate_baseline.py
language: python
signature: 'def validate_baseline(contract, approved_ref, repo_root="."):'
test_command: 'python -m unittest tests/test_validate_baseline.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: 'tests/test_validate_baseline.py'
tests_sha256: '63bec97a5c3ca5b339d22bd2d8c59a742f75138a28a07f4e0e122e154b5d6cec'
touch_only: ['scripts/validate_baseline.py']
deps_allowed: ['stdlib', 'vendored-codex-security']
forbids: ['llm']
---

## Intent
Aplicar la [validacion](../validacion.md) a la evidencia local del tablero.

## Interface
`validate_baseline(contract, approved_ref, repo_root)` devuelve diferencias o falla si la referencia es invalida.

## Invariants
- Re-sellar contrato y test no evade una referencia aprobada distinta.
- No modificar el repositorio ni la referencia.
- Normalizar LF igual que el validador de contratos.

## Examples
- Mismos archivos aprobados -> cero diferencias.
- Test y hash modificados -> dos diferencias.

## Do / Don't
- DO: resolver git mediante argumentos, sin shell.
- DON'T: elegir automaticamente HEAD como referencia aprobada.

## Tests
Oraculo sellado antes de implementar.

## Constraints
- PARAR y reportar si no existe el commit aprobado.
