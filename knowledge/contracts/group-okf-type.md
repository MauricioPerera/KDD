---
type: 'Task Contract'
title: 'Tipo OKF para contratos de grupo'
description: 'Reconoce el tipo de nodo Group Contract preservando la validacion OKF existente.'
tags: ['okf', 'groups', 'validation']
task: group-okf-type
intent: 'Admitir contratos de grupo como nodos OKF sin relajar otros tipos.'
target: scripts/validate_okf.py
signature: 'def validate_okf(knowledge_dir):'
test_command: 'python -m unittest tests.test_group_contracts'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: 'tests/test_group_contracts.py'
tests_sha256: 'b14c8f69cbd4baaae35fc3932fbe6bb9be99cac4632060290f9d59fd4de251e7'
touch_only: ['scripts/validate_okf.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent
Aplicar el tipo aprobado en [OKF-SPEC](../OKF-SPEC.md) y
[contratos de grupo](../group-contracts.md).

## Interface
Conservar API y CLI del validador OKF.

## Invariants
- Reconocer `Group Contract` ademas de los cinco tipos ya admitidos.
- Conservar reglas de metadatos, enlaces y alcance del indice.

## Examples
- Nodo de grupo completo y enlazado -> PASS.
- Tipo desconocido -> ERROR.

## Do / Don't
- DO: conservar la interfaz y comportamiento anterior.
- DON'T: admitir tipos arbitrarios o debilitar el indice.

## Tests
La integracion real del CLI esta en `tests/test_group_contracts.py`; los
oraculos OKF anteriores se conservan.

## Constraints
PARAR y reportar si es necesario relajar las otras reglas OKF.
