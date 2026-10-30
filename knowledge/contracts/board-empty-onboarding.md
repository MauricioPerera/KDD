---
type: 'Task Contract'
title: 'Arranque de Board sin tareas ficticias'
description: 'Conservar el almacenamiento local existente y comenzar vacio cuando no hay tareas.'
tags: ['board', 'onboarding', 'integration']
task: board-empty-onboarding
intent: 'Evitar que el tablero cree tareas de ejemplo durante su arranque.'
target: tools/kdd-board/src/server.ts
language: typescript
signature: 'createServer(apiToken)'
test_command: 'python -m unittest tests/test_board_onboarding_audit.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 250
  params_max: 5
tests: tests/test_board_onboarding_audit.py
tests_sha256: 'afeabde4583eda4a706cbcc5ccaf6485ef8c4a720095267b3a2bad228764713a'
touch_only: ['tools/kdd-board/src/server.ts']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
La [integracion del tablero](../board-git.md) debe presentar solo tareas reales.

## Interface
Un proyecto sin Git inicia en modo legacy con las tareas existentes, si las hay.
Una copia nueva inicializada con el inicializador real tambien inicia vacia.

## Invariants
No crear ejemplos ni reescribir un almacenamiento vacio. Conservar tareas y
autenticacion existentes, reinicios y comportamiento Git. No importar datos
legacy al diario Git ni crear cambios fuera del proyecto.

## Examples
- Sin archivo JSON: lista vacia antes y despues de reiniciar.
- Un archivo JSON vacio sigue vacio y sus bytes permanecen intactos.

## Do / Don't
- DO: comprobar HTTP autenticado y el inicializador real.
- DON'T: eliminar datos existentes ni fabricar commits.

## Tests
El oraculo usa procesos Node y peticiones HTTP reales, archivos y Git real.

## Constraints
Conservar Ubuntu, Windows, la suite existente y sus dos pasadas. PARAR y reportar si
resolver exige una nueva aprobacion de oraculos o cambios de proteccion.
