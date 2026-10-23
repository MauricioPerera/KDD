---
type: 'Task Contract'
title: 'Diario canonico Git de KDD Board'
description: 'Integrar lecturas OKF de main y mutaciones con commits a traves de HTTP y WebMCP.'
tags: ['ccdd', 'git', 'kdd-board']
task: board-git-journal
intent: 'Conectar KDD Board al coordinador canonico de tareas Git.'
target: tools/kdd-board/src/git-task-store.ts
language: typescript
signature: 'GitTaskStore(projectDir)'
test_command: 'node --test tools/kdd-board/tests/git-board.test.ts'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tools/kdd-board/tests/git-board.test.ts'
tests_sha256: 'a0eebee194402e2da318f4d24373219f477a746bf24821523af5dfd8a073f899'
touch_only: ['tools/kdd-board/src/git-task-store.ts', 'tools/kdd-board/src/git-bridge.ts', 'tools/kdd-board/src/git-api.ts', 'tools/kdd-board/src/server.ts', 'scripts/run_board.ps1', '.github/workflows/validate.yml']
deps_allowed: ['node', 'zod', 'fastwebmcp']
forbids: ['llm', 'network']
---

## Intent
Aplicar la [integracion Git](../board-git.md) sin duplicar el
[modelo de estados](../data_models/git-task.md) en almacenamiento local.

## Interface
`GitTaskStore(projectDir)` ofrece list, get, history, contracts, create y
transition. HTTP y WebMCP comparten la instancia y los esquemas documentados.

## Invariants
- Leer nodos y contratos confirmados de main, incluso desde otra rama.
- No inicializar JSON ni ejemplos en repositorios Git; errores fallan cerrados.
- Delegar commits, lock, aprobacion, ramas y evidencia al coordinador Python.
- Preservar SHA aprobado explicito, assignee y reason segun la arista.
- Rechazar saltos, reintentos ya confirmados, main sucio y cierre sin prueba real.
- Mantener autenticacion local y comprobacion de origen existentes.

## Examples
- POST create -> commit backlog; PATCH ready con SHA aprobado -> commit ready.
- Una rama no integrada o tests fallidos impiden done y no producen commit.

## Do / Don't
- DO: ejecutar subprocess sin shell con raiz de proyecto fijada por servidor.
- DON'T: escoger HEAD como aprobacion ni copiar nodos desde el working tree.

## Tests
El oraculo congelado usa repositorios Git temporales reales para comprobar
proyecciones, todas las aristas, pruebas, locks, HTTP y WebMCP.

## Constraints
- PARAR y reportar si se requieren nuevos permisos remotos o cambiar oraculos existentes.
