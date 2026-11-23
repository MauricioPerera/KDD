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
tests_sha256: '46ecd29bbd3839bb9bb22875688274489501e03542c39622d12ccb7a9891a388'
touch_only: ["scripts/optional_evidence.py"]
deps_allowed: []
forbids: ['llm']
---

## Intent
Validar la estructura minima de la evidencia obligatoria antes de declarar PASS. El alcance sigue [evidencia requerida](optional-evidence.md).

## Interface
Los comandos check y summary conservan su CLI y estados. Para privacidad, accesibilidad, vigencia y observabilidad obligatorias, validar el tipo de documento de la capa, schemaVersion igual a 1.0, scanId de escaneo real no vacio y findings como arreglo explicito. Una salida exitosa del validador no sustituye estos campos.

## Invariants
Mantener la compatibilidad opcional y las garantias existentes de security, compliance, test-coverage y quality. Un arreglo explicito vacio puede representar cero hallazgos. Los escaneos de ejemplo siguen sin ser evidencia real.

## Examples
- Un escaneo obligatorio con findings ausente o null devuelve FAIL.
- Un escaneo obligatorio con version, identificador y arreglo vacio valido conserva PASS.

## Do / Don't
- DO: reusar el punto de entrada y los controles existentes.
- DON'T: Evitar duplicar las reglas de severidad o cambiar el workflow.

## Tests
Cada caso ejecuta el validador existente y el resumen con su outcome comprobado. Rechazar campos ausentes o invalidos y conservar el caso positivo en las cuatro capas.

## Constraints
Aprobar el SHA del baseline antes de implementar. PARAR y reportar si se
requiere cambiar controles remotos, el runtime confiable u oraculos previos.
