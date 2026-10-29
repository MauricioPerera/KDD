---
type: 'Task Contract'
title: 'Actualizar contratos Git durante la sesion de Board'
description: 'Mantener seleccionable el catalogo confirmado de main.'
tags: ['board', 'git', 'integration']
task: board-contract-refresh
intent: 'Refrescar los contratos al cambiar main sin perder la seleccion valida.'
target: tools/kdd-board/public/git-board.js
signature: 'configure(api)'
test_command: 'python -m unittest tests/test_board_runtime_safety.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 250
  params_max: 5
tests: tests/test_board_runtime_safety.py
tests_sha256: 'ad1a0d516f5a471c26de4122c873cb445c32a0a29dbaca278d7c6171fc6ea6c5'
touch_only: ['tools/kdd-board/public/git-board.js']
deps_allowed: ['node', 'git']
forbids: ['llm']
---

## Intent
La [integracion Git](../board-git.md) usa contratos confirmados en main y no
debe congelar el catalogo al abrir el tablero.

## Interface
Al refrescar el tablero se reconcilia el catalogo de main. Una seleccion aun
valida se conserva; una seleccion eliminada deja de poder usarse. Una falla de
lectura no reemplaza el ultimo catalogo valido con datos parciales.

## Invariants
Solo se incluyen contratos confirmados; no se modifica Git ni se mezclan
resultados de una lectura fallida. El modo legacy mantiene su comportamiento.

## Examples
- Un contrato confirmado despues del arranque se puede seleccionar sin recargar.
- Un contrato borrado de main desaparece al refrescar.

## Do / Don't
- DO: integrar Git, HTTP autenticado y el codigo real de interfaz.
- DON'T: sustituir el catalogo de main por el directorio de trabajo.

## Tests
El oraculo sellado vincula el helper Node, un repositorio temporal y el servidor
real; la interfaz se ejercita con DOM simulado, no con un navegador renderizado.

## Constraints
Conservar Ubuntu/Windows, la cobertura y las dos pasadas. PARAR y reportar si fuera
necesario alterar una proteccion remota o un oraculo previamente aprobado.
