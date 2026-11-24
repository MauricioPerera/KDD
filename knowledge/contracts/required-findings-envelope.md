---
type: 'Task Contract'
title: "Evidencia minima de escaneos obligatorios"
description: "Rechazar escaneos obligatorios que omiten los campos requeridos de su esquema."
tags: ['audit', 'integration', 'quality']
task: required-findings-envelope
intent: "Validar la estructura minima de la evidencia obligatoria antes de declarar PASS."
target: scripts/optional_evidence.py
signature: "def evaluate_layers(layers, required, environ, summary=False)"
test_command: "python -m unittest tests.test_required_findings_envelope"
test_runner: python-unittest
oracle_files: ["tests/test_required_findings_envelope.py", "knowledge/data_models/privacy/findings.schema.json", "knowledge/data_models/accessibility/findings.schema.json", "knowledge/data_models/dependency-eol/findings.schema.json", "knowledge/data_models/observability/findings.schema.json"]
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_required_findings_envelope.py"
tests_sha256: '2ade9a63acde98728c43d00bbb4718a19491f6c3c970c6cf6a2721723420df3e'
touch_only: ["scripts/optional_evidence.py"]
deps_allowed: []
forbids: ['llm']
---

## Intent
Comprobar la [evidencia obligatoria](optional-evidence.md).

## Interface
Check y summary validan el tipo, version 1.0, scanId no vacio y findings como arreglo.

## Invariants
Aplicar a privacidad, accesibilidad, vigencia y observabilidad requeridas. Preservar las otras capas y modos.

## Examples
- Ausencia de datos produce FAIL aunque el validador salga con 0.
- Un arreglo vacio explicito con metadatos validos pasa.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
CLI de validacion real con controles de forma y outcome.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
