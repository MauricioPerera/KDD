---
type: 'Task Contract'
title: 'Referencias canonicas en las herramientas locales de calidad'
description: 'Exigir commits inmutables en approve y build_baseline antes de ejecutar checks o emitir manifiestos.'
tags: ['quality', 'git', 'integration']
task: quality-ref-canonical
intent: 'Conservar la identidad revisada al usar las APIs y CLI locales de calidad.'
target: scripts/verify_quality.py
language: python
signature: 'def approve(root, policy_path, reference):'
test_command: 'python -m unittest tests/test_quality_ref_canonical.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_quality_ref_canonical.py
tests_sha256: '6e6f88255211e32c2f5e184580ecef76faf6712d19537e5d54efe8bede89bcf4'
touch_only: ['scripts/verify_quality.py', 'scripts/quality_baseline.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---
## Intent
Aplicar la [identidad nativa de calidad](../task-quality-fixture-remediation.md).
## Interface
Conservar approve/build_baseline y ambas CLI. Solo un OID canonico completo
de commit nativo existente puede iniciar checks o producir un manifiesto.
## Invariants
Rechazar aliases y otros tipos Git antes de ejecutar checks; conservar SHA-1,
SHA-256, hashes y dos vueltas. Un alias no se vuelve aprobado al moverlo.
## Examples
- SHA aprobado y producto permitido: calidad pasa dos veces.
- Rama movida a un oraculo cambiado: REJECT, sin ejecutar checks.
## Do / Don't
- DO usar objetos reales y el SHA original como control independiente.
- DON'T tratar HEAD^0 o un tag anotado como commit aprobado por su longitud.
## Tests
Oraculo nuevo prueba API y CLI, formatos nativos, objetos, aliases y ausencia
de efectos al rechazar; no depende de un repo Git en el checkout fuente.
## Constraints
PARAR y reportar si requiere cambiar oraculos anteriores, selector o runtime.
