---
type: 'Task Contract'
title: 'Reducir complejidad del validador de skills'
description: 'Cumplir los budgets existentes de skills conservando dialecto y findings.'
tags: ['skills', 'quality', 'budget', 'integration']
task: skills-validator-complexity
intent: 'Reducir complejidad del gate de skills sin alterar su comportamiento.'
target: scripts/validate_skills.py
signature: 'def validate_skills(skill_dirs) -> list:'
test_command: 'python -m unittest tests.test_skills_complexity'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_skills_complexity.py
tests_sha256: '19612bfd42dafc129b7ed8dd14293047268d25c0eb6f69e7b3f4c8be06f8daa6'
touch_only: ['scripts/validate_skills.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

## Intent
Reducir los hallazgos del [gate de skills](skills-gate.md) sin relajar sus
budgets ni sustituir el medidor. Es parte de la deuda registrada en
[remediacion](../audit-p1-p2-remediation.md).

## Interface
Preservar API, CLI, codigo de salida, orden, textos y forma de findings; los
helpers privados pueden reorganizarse dentro del mismo modulo.

## Invariants
- Todas las funciones cumplen cyclomatic_max 10 y nesting_max 4 del contrato
  previo, incluidos helpers; no elevar limites ni excluir funciones.
- Preservar exactamente el dialecto compartido con validate_okf/contratos y los
  oraculos sellados y fixtures actuales. No introducir dependencias ni cache.
- Mantener conteo, errores e INFO, rutas, enlaces y determinismo en ambos SO.
- Conservar inventario, Ubuntu/Windows y dos pasadas de la suite; sin nuevos SKIP.

## Examples
- Dos skills con igual nombre generan un solo NAME_DUP ordenado y CLI exit 1.
- Un directorio ausente informa DIR_MISSING y CLI exit 0.

## Do / Don't
- DO comprobar CLI, sistema de archivos y findings reales.
- DON'T modificar el oraculo previo, subir budgets o delegar logica a otro modulo.

## Tests
`tests/test_skills_complexity.py` mide el budget y usa siete integraciones con
archivos y procesos reales. Se conservan las pruebas anteriores de skills y de
coherencia del parser; una copia inicializada no necesita .git para ejecutarlo.

## Constraints
PARAR y reportar si se necesita modificar oraculos previos, runtime, workflow o
protecciones remotas. Baseline humano obligatorio antes de implementar.
