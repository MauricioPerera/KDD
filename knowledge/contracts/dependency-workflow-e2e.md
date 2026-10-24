---
type: 'Task Contract'
title: 'Piloto de cuatro tareas como regresion real'
description: 'Repetir bootstrap, Board autenticado, dependencias, commits, evidencias y calidad CI.'
tags: ['quality', 'maintenance', 'verification']
task: dependency-workflow-e2e
intent: 'Repetir bootstrap, Board autenticado, dependencias, commits, evidencias y calidad CI.'
target: scripts/tasks.py
language: python
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests/test_dependency_workflow_e2e.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_dependency_workflow_e2e.py
tests_sha256: 'b64e9fc60bfc1892f25554c35a44bc4e016018050d546b3ba01208d207a7e5ad'
touch_only: ['scripts/tasks.py', 'scripts/task_git.py', 'scripts/validate_tasks.py', 'tools/kdd-board/src/git-task-store.ts']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Usar copias reales de plantilla, procesos y servidor HTTP real; cuatro contratos/oraculos propios y baseline simulado solo en temporales. Verificar cierre y calidad desde baseline inicial.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- A cerrada permite B/C; ambas cerradas permiten D y cuatro evidencias validas.
- D con solo B cerrada -> rechazo observable y ningun commit o rama nuevos.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tests/test_dependency_workflow_e2e.py. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
