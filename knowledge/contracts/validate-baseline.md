---
type: 'Task Contract'
title: 'Referencia aprobada del oraculo'
description: 'Detectar cambios de todos los contratos y oráculos respecto de un commit aprobado.'
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
tests_sha256: '7af7a1cc20d2568578397d089334a920ed15a8214d9e2b5ec1d2819ff51f8c91'
touch_only: ['scripts/validate_baseline.py']
deps_allowed: ['stdlib', 'vendored-codex-security']
forbids: ['llm']
---

## Intent
Aplicar la [validacion](../validacion.md) a la evidencia local del tablero.

## Interface
`validate_baseline(contract, approved_ref, repo_root)` devuelve diferencias de una
tarea o falla si la referencia es inválida. `validate_all_baselines(approved_ref,
repo_root, contracts_dir)` inspecciona todos los contratos, también altas y
bajas. El CLI acepta exactamente un contrato o `--all` y exige `--approved-ref`.

## Invariants
- Re-sellar contrato y test no evade una referencia aprobada distinta.
- Un contrato nuevo o eliminado falla contra la referencia aprobada.
- No modificar el repositorio ni la referencia.
- Normalizar LF igual que el validador de contratos.

## Examples
- Mismos archivos aprobados -> cero diferencias.
- Test y hash modificados -> dos diferencias.
- `--all --approved-ref SHA` -> verifica todos los contratos y sus oráculos.

## Do / Don't
- DO: resolver git mediante argumentos, sin shell.
- DON'T: elegir automaticamente HEAD como referencia aprobada en el perfil.

## Tests
Oraculo sellado antes de implementar.

## Constraints
- PARAR y reportar si no existe el commit aprobado.
