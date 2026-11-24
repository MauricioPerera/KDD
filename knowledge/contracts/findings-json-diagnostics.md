---
type: 'Task Contract'
title: 'Diagnosticos JSON de findings'
description: 'Clasificar el formato de findings con los codigos de la CLI.'
tags: ['audit', 'quality']
task: findings-json-diagnostics
intent: "Clasificar evidencia JSON invalida con un diagnostico estable."
target: scripts/validate_dependency_eol_findings.py
signature: "def main(argv=None)"
test_command: "python -m unittest tests.test_findings_json_diagnostics"
test_runner: python-unittest
oracle_files: ['tests/test_findings_json_diagnostics.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: "tests/test_findings_json_diagnostics.py"
tests_sha256: 'f186236ffb27560a8fd2c865ee19d36c499e1098d4c680bee8db65cbb02cc594'
touch_only: ['scripts/validate_dependency_eol_findings.py', 'scripts/validate_accessibility_findings.py', 'scripts/validate_compliance_findings.py', 'scripts/validate_observability_findings.py', 'scripts/validate_privacy_findings.py', 'scripts/optional_evidence.py']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
P2-23, P2-24 y P3-11.

## Interface
Una raiz que no sea objeto devuelve 2 con DOCUMENT_TYPE.
En vigencia, JSON truncado devuelve 2 con PARSE_ERROR.

## Invariants
El [precheck](optional-evidence.md) rechaza NaN e infinitos.
Conserva la [evidencia obligatoria](required-findings-envelope.md).

## Examples
- Arreglo vacio: DOCUMENT_TYPE.
- Objeto con findings vacio conserva el resultado de la politica.

## Do / Don't
- DO: conservar bytes y diagnosticar sin traceback.
- DON'T: exigir metadatos nuevos.

## Tests
CLI con archivos temporales.

## Constraints
PARAR y reportar si falta el baseline humano.
