---
type: 'Task Contract'
title: 'Entrada de revision previa a la aprobacion de baseline'
description: 'Conectar el registro de riesgo a quality_baseline sin alterar su API historica.'
tags: ['baseline', 'review', 'integration']
task: baseline-review-entrypoint
intent: 'Ofrecer una preparacion revisada del candidato antes de su aprobacion externa.'
target: scripts/quality_baseline.py
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests.test_baseline_review_entrypoint'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_baseline_review_entrypoint.py
tests_sha256: '4daf86a379fbb5d4a675d4f912a6abb453796dfe0d72ca63c5bc318b7338a174'
oracle_files: ['tests/test_baseline_review_entrypoint.py', 'tests/test_baseline_risk_review.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/quality_baseline.py', '.agents/AGENTS.md', '.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md', 'knowledge/quality-approval.md', 'knowledge/quickstart.md', 'knowledge/supervision-humana.md']
deps_allowed: ['stdlib', 'verify_quality', 'baseline_review']
forbids: ['network', 'llm']
---

## Intent
Integrar la [revision proporcionada](../baseline-risk-review.md) en la
[preparacion del baseline](quality-baseline.md) y en el procedimiento de agentes.

## Interface
Modo previo: `python scripts/quality_baseline.py --repo-root DIR --base-ref
BASE --candidate-ref SHA --review INFORME.json`. Los tres flags de revision
son obligatorios juntos y excluyen --policy/--approved-ref. Devuelve exactamente
el JSON de verify_review; exit 0/1/2 segun el protocolo.
Modo historico: --policy y --approved-ref obligatorios juntos, sin flags de
revision; conservar build_baseline(repo_root, policy_path, approved_ref) y
su resultado, sin afirmar review_ready. Errores de uso salen 2.
La estructura del resultado historico se conserva. La correccion de
[hashes exactos](quality-manifest-bytes.md) define los valores de identidad de
blobs; no normalizar contenido binario ni mantener un hash historico incorrecto.

## Invariants
- No crear un baseline aprobado, registro externo, commit o ref desde este modo.
- Fallar cerrado si se proporciona un informe pero falta cualquier identidad.
- No ignorar un informe invalido, ajeno, con revision ausente o riesgo insuficiente.
- Conservar hashes de politica y protected y el rechazo de HEAD del modo anterior.
- El flujo nuevo se documenta antes de pedir aprobacion de un baseline nuevo.
- Conservar los perfiles historicos, los 19 gates y Ubuntu/Windows con dos suites.

## Examples
- Candidato con informe completo -> review_ready true, sin approved_ref.
- Candidato sin informe o mezcla de modos -> error de uso, sin manifiesto.
- Referencia aprobada historica explicita -> mismo manifiesto anterior.

## Do / Don't
- DO separar revision lista de aprobacion externa del SHA.
- DON'T introducir rondas LLM, nuevos gates o autoaprobaciones.

## Tests
Subprocesos Python y repositorios Git reales verifican ambos modos, sus errores,
read-only, informe ajeno y clon de una copia inicializada sin .git. Los oraculos
anteriores de quality_baseline quedan byte por byte intactos.

## Constraints
PARAR y reportar si se necesita implementar sin baseline revisado. La publicacion,
la aprobacion del runtime o cambios de proteccion requieren alcance posterior.
