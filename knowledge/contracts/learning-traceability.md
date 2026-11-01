---
type: 'Task Contract'
title: 'Aprendizaje con decisiones y pruebas versionadas'
description: 'Aprendizaje con decisiones y pruebas versionadas con alcance mecanico y revision humana explicitos.'
tags: ['governance', 'provenance', 'verification']

task: learning-traceability
intent: 'Aprendizaje con decisiones y pruebas versionadas.'
target: scripts/validate_learning.py
signature: 'def validate(root, ledger_path, approved_ref, observed_ref=None, require_accepted=False):'
test_command: 'python -m unittest tests.test_learning_traceability'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_learning_traceability.py
tests_sha256: 'e4fcdf8dcf6b2f8b69633f6eeb3a1138dcef9bbe9754d69b73a88dbba831cce5'
touch_only: ['scripts/validate_learning.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm', 'product-execution']
---

## Intent

Cumplir la [propuesta de contexto y aprendizaje](../context-learning-provenance.md)
y el [objetivo](../kdd-governance-closure.md), conservando la
[aprobacion](../quality-approval.md) y sus limites de confianza.

## Interface

Nuevo lector de solo lectura y CLI JSON --ledger --approved-ref --observed-ref,
--require-accepted y --require-execution. El placeholder del baseline no tiene
implementacion. La referencia externa aprobada es OID canonico, nunca HEAD.

## Invariants

- Ledger y artefactos se leen de Git observado/aprobado, no del checkout corregido.
- Entrada accepted identica en ledger aprobado; finding, decision y tests versionados.
- Verificar esquema, IDs unicos, paths exactos, blobs regulares y refs canonicos
  antecesores de aprobacion/observacion. Rechazar symlink, gitlink y escape.
- Hashes LF correctos y mismos contenidos en observed_ref; cambio -> LEARNING_STALE.
- No inferir aprobacion de approved_by ni permitir autoaceptacion del candidato.
- JSON determinista con complete, status, referencias, cobertura, entradas y findings.
- Enlaces de test: reference_verified=true, execution_observed=false. No ejecutar
  ni importar producto; --require-execution es LEARNING_UNSUPPORTED en este perfil.
- Draft -> PENDING, legado -> LEGACY_UNVERIFIED, sin inventar referencias.
  --require-accepted exige al menos una aceptada y ningun pendiente/incompleto.
- Preservar refs, indice y checkout; el runner/Git y la seleccion externa son confiables.

## Examples

- Hallazgo, decision y tests aprobados -> enlaces verificados, no ejecucion de tests.
- Candidato promueve draft -> LEARNING_APPROVAL; decision cambiante -> LEARNING_STALE.
- Referencia valida no prueba coherencia, comprension ni generalizacion del aprendizaje.

## Do / Don't

- DO conservar evidencia real, versiones y alcance observado.
- DON'T presentar una identidad o referencia como comprension, semantica o ejecucion.

## Tests

Oraculo nuevo tests/test_learning_traceability.py con filesystem/Git reales. La extension de
inicializacion revisa unicamente las tres expectativas exactas documentadas
del oraculo anterior; los demas contratos y tests congelados se conservan.

## Constraints

PARAR y reportar si hace falta otra fuente, oraculo, dependencia, ampliar budgets,
modificar workflows/protecciones o la confianza del runner. Aprobar baseline
antes de implementar y esperar el CI dual-OS 2x de KG-4. No inferir aprobacion
humana ni certificacion retrospectiva de ejecucion o comprension.
