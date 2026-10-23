---
type: 'Task Contract'
title: 'Interfaz del tablero para tareas Git'
description: 'Crear tareas y solicitar transiciones canonicas con datos explicitos e historial visible.'
tags: ['ccdd', 'git', 'kdd-board', 'ui']
task: board-git-ui
intent: 'Presentar las tareas OKF y confirmar transiciones solo tras su commit.'
target: tools/kdd-board/public/git-board.js
language: javascript
signature: 'KddGitBoard.configure(api), render(task, api, refresh), createInput(input)'
test_command: 'node --test tools/kdd-board/tests/git-board-ui.test.ts'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tools/kdd-board/tests/git-board-ui.test.ts'
tests_sha256: '065a71345cf20c52c25db6808b7ddd1b11182cc0ab080204c4ef43afa4f181c6'
touch_only: ['tools/kdd-board/public/git-board.js', 'tools/kdd-board/public/app.js', 'tools/kdd-board/public/index.html', 'tools/kdd-board/public/style.css']
deps_allowed: []
forbids: ['llm']
---

## Intent
Presentar la [integracion Git](../board-git.md) mediante formularios coherentes
con el [modelo de tareas](../data_models/git-task.md).

## Interface
`configure(api)` descubre modo y catalogo; `createInput(input)` produce el
payload canonico; `render(task, api, refresh)` presenta tarea, historial y acciones.

## Invariants
- Creacion exige ID y contrato de main; sin prioridad ficticia ni asignacion anticipada.
- Las acciones ofrecen solo aristas legales y recogen SHA, propietario o motivo.
- No declarar exito ni refrescar como confirmado antes del commit retornado.
- Mostrar errores sin cambiar estado local; polling preserva formularios activos.
- Renderizar campos e historial como datos escapados.
- El navegador registra tools Git conservando todos sus argumentos canonicos.

## Examples
- Backlog ofrece ready y campo de SHA aprobado; no ofrece done.
- TASK_DIRTY se muestra al usuario y la tarjeta conserva su estado confirmado.

## Do / Don't
- DO: mostrar rama, aprobacion, evidencia e historial de commits.
- DON'T: ofrecer edicion directa de estado o un enlace de contrato mutable.

## Tests
Oraculo congelado con DOM controlado para formularios, errores, seguridad,
polling y transporte WebMCP del navegador.

## Constraints
- PARAR y reportar si cumplir requiere cambiar oraculos existentes.
