---
type: 'Task Contract'
title: 'Comprobaciones frescas de main con dos procesos Git'
description: 'Reducir consultas repetidas del coordinador preservando branch, raiz, limpieza y deteccion de carreras.'
tags: ['git', 'performance', 'integration']
task: task-main-read-budget
intent: 'Reducir a dos las consultas Git reales de cada comprobacion fresca de main.'
target: scripts/task_git.py
language: python
signature: 'def _clean_main(root, expected=None):'
test_command: 'python -m unittest tests/test_task_main_read_budget.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_task_main_read_budget.py
tests_sha256: '3e314bbae04bf190a8745311a74934af9bc213af9a4c9075d611e4cf90f30ee5'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Cumplir el [presupuesto de lecturas](../audit-remediation-approval-mutation-board.md)
y conservar la [auditoria Git](../git-tasks.md).
## Interface
Mismo resultado de _clean_main, errores TASK_MAIN/TASK_DIRTY/TASK_RACE y CLI.
No cachear rama, working tree, indice, untracked ni HEAD entre invocaciones.
## Invariants
- Dos procesos Git como maximo por llamada exitosa, medidos con Trace2 real.
- Exigir raiz exacta, main, limpieza completa y el HEAD esperado actual.
- Detectar cambios de indice, working tree, untracked y HEAD en una misma operacion.
- No alterar datos de usuario, ramas, commits, configuracion ni limites existentes.
## Examples
- Doce comprobaciones limpias -> mismo SHA y como maximo 24 procesos Git.
- Tras un commit externo o un archivo nuevo -> rechazo fresco, sin PASS cacheado.
## Do / Don't
- DO: medir procesos y el flujo real antes/despues; conservar dos pasadas y SO.
- DON'T: decidir correccion por segundos, subir limites o omitir pruebas.
## Tests
Oraculo Git/Trace2 nuevo con limpieza, suciedad staged/unstaged/untracked,
detached/otra rama, subdirectorio, HEAD esperado y contextos cacheados.
## Constraints
PARAR y reportar si requiere cambiar un oraculo previo o runtime/workflows/
protecciones. Medicion del CI exige autorizacion posterior de publicacion.
