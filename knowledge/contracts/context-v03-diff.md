---
type: 'Task Contract'
title: 'Comparacion conservadora de contextos CCDD v0.3'
description: 'Detecta regresiones de guardrails y cambios sensibles sin afirmar aprobacion criptografica.'
tags: ['context', 'ccdd', 'security']
task: context-v03-diff
intent: 'Comparar contextos contra una referencia suministrada por el operador.'
target: scripts/context_v03.py
signature: 'def main():'
test_command: 'python -m unittest tests.test_context_v03'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: 'tests/test_context_v03.py'
tests_sha256: 'e22f4dd536caf44d3ca8c95b70302fddfeddbb3c86c103c3d0a6361881684ed7'
touch_only: ['scripts/context_v03.py']
deps_allowed: ['stdlib', 'PyYAML', 'jsonschema']
forbids: ['network', 'llm', 'subprocess']
---

## Intent
Implementar el diff conservador definido en [compatibilidad](../context-v03-compat.md).

## Interface
CLI `diff <baseline-dir> <candidate-dir>` y salida JSON.

## Invariants
- Rechazar disminucion de guardrails, presupuesto o quorum y cambios de esquema.
- Bloquear cambios de estaticos firmados o de registros como `REVIEW_REQUIRED`.
- No acreditar identidad, quorum o integridad de la base aportada por el llamador.

## Examples
- Dos contratos identicos e integros -> PASS.
- Quitar un guardrail o modificar una politica firmada -> BLOCKED.

## Do / Don't
- DO: mantener y reportar limites explicitos.
- DON'T: aceptar una atestacion sin verificar su firma.

## Tests
Pruebas reales con directorios y mutaciones en `tests/test_context_v03.py`.

## Constraints
PARAR y reportar si se necesita atribuir aprobacion criptografica no implementada.
