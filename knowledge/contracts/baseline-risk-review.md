---
type: 'Task Contract'
title: 'Revision proporcional de un candidato exacto de baseline'
description: 'Clasificar un diff Git y validar un registro breve sin conceder aprobacion.'
tags: ['baseline', 'review', 'git', 'integration']
task: baseline-risk-review
intent: 'Comprobar la preparacion de una revision proporcional antes de aprobar el baseline.'
target: scripts/baseline_review.py
signature: 'def verify_review(repo_root, base_ref, candidate_ref, review_json):'
test_command: 'python -m unittest tests.test_baseline_risk_review'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_baseline_risk_review.py
tests_sha256: '9b632fc89ab50fc82727e19d85d6cee6af01cb93ede88190fc675806fae24c54'
oracle_files: ['tests/test_baseline_risk_review.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/baseline_review.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [revision anterior al baseline](../baseline-risk-review.md),
complementando la [aprobacion humana](../quality-approval.md).

## Interface
`inspect_change(repo_root, base_ref, candidate_ref)` devuelve un dict con
schema_version 1, base_commit, candidate_commit, candidate_tree, risk_floor,
changes y review_ready false. Cada cambio tiene path y before/after (null
o {mode, oid}). `verify_review(repo_root, base_ref, candidate_ref, review_json)`
agrega risk, required_reviewers, sources y findings mecanicos con code y message.
ReviewError(ValueError) identifica datos o Git invalidos. CLI acepta --repo-root,
--base-ref, --candidate-ref y --review opcional; imprime un unico JSON en stdout.
Codigos de NOT_READY: RISK_TOO_LOW, REVIEW_INDEPENDENCE, REVIEW_INCOMPLETE,
LENS_MISSING, LENS_BLOCKED, SOURCE_COVERAGE, OPEN_FINDING y DECISION_INVALID.
Los errores usan REVIEW_SCHEMA, REVIEW_SOURCE, REVIEW_IDENTITY, REVIEW_REF,
REVIEW_HISTORY o REVIEW_GIT segun su causa, sin producir un resultado parcial.

## Invariants
- Aplicar exactamente el esquema, pisos, perspectivas y decisiones del nodo fuente.
- Canonizar solo identidades Git completas; no resolver alias como aprobaciones.
- El candidato ejecutado nunca decide su nivel minimo ni elimina rutas del diff.
- Leer Git real sin checkout ni ejecutar hooks, programas, diffs externos o codigo del candidato.
- Conservar branch, refs, config, indice y bytes del working tree, incluso al rechazar.
- Un error Git o fuente ausente/alias no produce exito parcial; sin caches de PASS.
- Los scripts conservan ASCII y stdlib. No agregar procesos de modelos a CI.

## Examples
- Documento ordinario y una revision completa -> low y review_ready true.
- Prueba nueva -> medium; cambio de oraculo existente -> high.
- Cambio de workflow declarado low -> NOT_READY por riesgo insuficiente.
- Un revisor ausente o un major abierto -> NOT_READY aunque el resto pase.
- Un informe valido para otro commit/arbol -> ReviewError, sin aprobar nada.

## Do / Don't
- DO revisar fuentes del commit exacto, incluido el lado base de un borrado.
- DON'T aceptar riesgos automaticamente, inferir identidad real o llamar approved a review_ready.

## Tests
Integraciones Git reales y procesos CLI cubren los ejemplos y rechazos del
protocolo en ambos sistemas. No se simula un PASS del runner ni de un revisor.
El archivo nuevo no modifica los 2138 IDs anteriores ni sus aserciones.

## Constraints
PARAR y reportar si se necesita implementar sin revision del SHA de contratos y
oraculos. No cambiar runtime, workflows, protecciones ni otros oraculos.
No presentar los metadatos declarados como prueba de aislamiento del host.
