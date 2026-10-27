---
type: 'Task Contract'
title: 'Aprobaciones de tarea fijadas a commits nativos reales'
description: 'Rechazar nombres moviles y objetos ajenos como aprobaciones, preservando SHA-1 y SHA-256.'
tags: ['git', 'quality', 'integration']
task: task-approval-identity
intent: 'Fijar la identidad del commit aprobado antes de publicar o validar una tarea.'
target: scripts/task_git.py
language: python
signature: 'def contract_metadata(root, data, revision, *, committed_only=False):'
test_command: 'python -m unittest tests/test_task_approval_identity.py'
budget:
  cyclomatic_max: 20
  nesting_max: 5
  lines_max: 180
  params_max: 5
tests: tests/test_task_approval_identity.py
tests_sha256: '49622594be356404a9f6a04010fe1447969b16d4f2a0cf0c79dbd6e9c9b338ac'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Cumplir la [identidad de aprobacion](../audit-remediation-approval-mutation-board.md)
y la [revision humana](../quality-approval.md).
## Interface
Conservar CLI, mutate, contract_metadata y campos Task. No deducir un baseline.
## Invariants
- Exigir OID completo de un commit real, del formato nativo, identico al resuelto.
- Rechazar aliases hex moviles, tags, trees, abreviaciones y objetos ausentes.
- Rechazar antes de crear commits o ramas; auditar tambien datos persistidos.
- Conservar flujo SHA-1/SHA-256, ancestros, sellos, modos y limites Git existentes.
## Examples
- Rama 64-hex en SHA-1 -> TASK_APPROVAL y main intacto.
- Commit SHA-256 real aprobado -> ready/start/finish y evidencia verificable.
## Do / Don't
- DO: Git real, refs movidas y snapshots invalidos, sin respuestas Git simuladas.
- DON'T: fijar la rama al commit actual como aprobacion automatica.
## Tests
El oraculo sellado usa ambos formatos y verifica rechazo, ausencia de efectos,
registros heredados y un flujo completo con evidencia.
## Constraints
PARAR y reportar si requiere otro baseline, cambiar runtime, workflows o
protecciones. No modificar oraculos anteriores. Baseline humano antes de implementar.
