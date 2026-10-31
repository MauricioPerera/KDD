---
type: 'Task Contract'
title: 'Reducir complejidad del diario Git de tareas'
description: 'Cumplir los presupuestos vigentes de task_git conservando el diario y sus fronteras.'
tags: ['quality', 'budget', 'git', 'tasks', 'integration']
task: task-git-complexity
intent: 'Eliminar los excesos de task_git sin alterar comportamiento ni subir limites.'
target: scripts/task_git.py
signature: 'def mutate(repo_root, operation, task_id, options) -> dict:'
test_command: 'python -m unittest tests.test_task_git_complexity'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_task_git_complexity.py
tests_sha256: 'fe0164a9e5dc59ad5172ee423bac2e670db52b3d24b6b7ad94fe09549597ceba'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts', 'validate_tasks']
forbids: ['network', 'llm']
---

## Intent
Eliminar los doce hallazgos actuales de [diario Git](task-journal.md),
[artefactos confirmados](task-committed-artifacts.md) y
[lecturas frescas](task-main-read-budget.md), sin elevar sus presupuestos.

## Interface
Conservar las interfaces publicas, firmas y resultados de `mutate`, `commit_sha`,
`blob`, `blobs`, `read_nodes`, `read_tasks`, `history` y `contract_metadata`.
Helpers privados pueden cambiar si se preservan los contratos y sus llamadores.
`_publish` agrupa rama y mensaje en un solo par `(branch, message)`; el unico
llamador externo a produccion es el oraculo de frontera, adaptado para revision.

## Invariants
- Cumplir para todo `scripts/task_git.py` los limites mas estrictos existentes:
  ciclomaticidad 12, anidamiento 4, 100 lineas y cuatro parametros, incluidos
  helpers nuevos. No modificar limites ni excluir funciones del medidor.
- Conservar aprobacion, evidencia real, locks, rollback, errores y diario Git.
- Mantener identidad SHA-1/SHA-256, refs movibles frescas, cache de objetos
  inmutables, modos Git regulares y rechazo de enlaces en consultas historicas.
- Mantener comprobaciones frescas de main con hasta dos procesos Git por llamada,
  sin modificar producto, indice o ramas ajenas ante un rechazo.
- Mantener los oraculos existentes y su cobertura; solo el argumento de la
  llamada directa a `_publish` en `test_task_write_boundary.py` se adapta al
  par de publicacion, sin retirar pruebas ni aserciones. Conservar Ubuntu,
  Windows y dos pasadas completas.

## Examples
- Un hook Git real que rechaza un commit restaura el archivo y la rama creada.
- Un target historico con modo 120000 se rechaza aun con checkout regular.
- Una ref `main` movida se vuelve a resolver dentro de la misma cache.

## Do / Don't
- DO usar Git real, comprobar resultados y comparar el diagnostico contra main.
- DON'T subir limites, mover logica a archivos externos o alterar la semantica.

## Tests
El oraculo adicional comprueba presupuestos de los tres contratos existentes,
flujo CLI hasta evidencia y auditoria, objetos y refs SHA-1/SHA-256, enlace Git,
rollback con hook real y Trace2. Sus fixtures heredados permanecen congelados.

## Constraints
PARAR y reportar si el arreglo exige cambiar otro oraculo previo no revisado,
modificar runtime, workflows o protecciones, o si la comparacion revela
hallazgos nuevos o agravados.
