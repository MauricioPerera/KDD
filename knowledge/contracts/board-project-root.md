---
type: 'Task Contract'
title: 'Detectar la raiz Git real antes de abrir Board'
description: 'Rechazar un proyecto anidado que no coincide con la raiz Git detectada.'
tags: ['board', 'git', 'onboarding']
task: board-project-root
intent: 'Impedir que Board anuncie modo Git para un directorio que no puede mutar.'
target: tools/kdd-board/src/git-task-store.ts
language: typescript
signature: 'isGitProject(root: string): boolean'
test_command: 'python -m unittest tests/test_board_onboarding_audit.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 200
  params_max: 5
tests: tests/test_board_onboarding_audit.py
tests_sha256: 'afeabde4583eda4a706cbcc5ccaf6485ef8c4a720095267b3a2bad228764713a'
touch_only: ['tools/kdd-board/src/git-task-store.ts']
deps_allowed: ['node', 'git']
forbids: ['llm']
---

## Intent
La [integracion Git](../board-git.md) requiere la misma raiz para lectura y
mutaciones, sin convertir un error de Git en un tablero JSON.

## Interface
Una raiz Git propia valida conserva modo git; un directorio sin repositorio
conserva legacy. Un directorio dentro de otro repositorio se rechaza al arrancar
con TASK_PROJECT_ROOT y una indicacion para usar o inicializar la raiz correcta.

## Invariants
Sin crear JSON, commits ni tocar el repositorio padre al rechazar. Conservar
worktrees validos, deteccion de Git ausente y main inexistente sin fallback.

## Examples
- Raiz real con main: modo git y fuente main.
- Subdirectorio sin Git propio dentro de un padre: error TASK_PROJECT_ROOT.

## Do / Don't
- DO: comparar rutas reales y probar repositorios y procesos reales.
- DON'T: operar silenciosamente en un repositorio padre o degradar a JSON.

## Tests
El oraculo construye repositorios temporales, arranca el servidor y comprueba
ausencia de escrituras y commits en el caso rechazado.
Los dos fixtures HTTP legacy eligen un temporal fuera de Git usando un helper
compartido; una regresion real ejecuta cada uno con TEMP dentro de un repo.

## Constraints
Conservar las dos pasadas y la cobertura. PARAR y reportar si hace falta cambiar un
oraculo anterior sin revision o modificar protecciones remotas.
