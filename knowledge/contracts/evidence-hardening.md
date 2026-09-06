---
type: 'Task Contract'
title: 'Evidencia de seguridad verificable'
description: 'Rechazar escaneos sin sello y distinguir evidencia ausente.'
tags: ['ccdd', 'security']
task: evidence-hardening
intent: 'Validar la evidencia sellada antes de evaluar politicas de seguridad.'
target: scripts/validate_security_findings.py
language: python
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests/test_evidence_hardening.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: 'tests/test_evidence_hardening.py'
tests_sha256: '6ef7a8a07d1d0c6b793a34671c7468d71c7d432ca47653e83ec09e97c345b348'
touch_only: ['scripts/validate_security_findings.py', 'scripts/preflight.py', 'scripts/rule_hints.py']
deps_allowed: ['stdlib', 'vendored-codex-security']
forbids: ['llm']
---

## Intent
Aplicar la [validacion](../validacion.md) a la evidencia local del tablero.

## Interface
`main(argv)` conserva exit 0 para ausencia opcional y exit 2 para datos invalidos.

## Invariants
- Un archivo sin manifest sellado nunca pasa como evidencia.
- La validacion no escribe ni sella artefactos.
- Ausencia opcional se presenta como SKIP; ausencia requerida bloquea.

## Examples
- JSON minimo sin manifest -> exit 2.
- Directorio ausente con --required -> exit distinto de cero.

## Do / Don't
- DO: reutilizar el validador vendorizado de solo lectura.
- DON'T: regenerar el sello durante la verificacion.

## Tests
Regresiones selladas antes de implementar.

## Constraints
- PARAR y reportar si la validacion exige modificar el scan.
