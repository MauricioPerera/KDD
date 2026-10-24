---
type: 'Task Contract'
title: 'Concurrencia y recuperacion con worktrees'
description: 'Verificar trabajadores simultaneos, conflictos, locks y publicacion preservando commits.'
tags: ['quality', 'maintenance', 'verification']
task: task-worktree-integration
intent: 'Verificar trabajadores simultaneos, conflictos, locks y publicacion preservando commits.'
target: scripts/task_git.py
language: python
signature: 'def mutate(repo_root, operation, task_id, options):'
test_command: 'python -m unittest tests/test_task_worktree_integration.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_task_worktree_integration.py
tests_sha256: '3503ef8bc93375915db5a8f9601de375628324ad7b3e0199bc4059890fc7ca1a'
touch_only: ['scripts/task_git.py', 'scripts/validate_tasks.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Coordinador main y trabajadores en worktrees reales; barreras observables de dos procesos, bloqueo comun, conflicto/abort sin perdida y remoto bare con hook de proteccion.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- Trabajadores B/C simultaneos -> dos tips preservados e integrados sin reescritura.
- Lock tras interrupcion o push directo protegido -> rechazo; recuperacion explicita conserva archivos.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tests/test_task_worktree_integration.py. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
