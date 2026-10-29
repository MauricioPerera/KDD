---
type: 'Task Contract'
title: 'Preservar el tablero ante fallos de lectura'
description: 'Mantener la ultima vista valida y mostrar el error del coordinador.'
tags: ['board', 'errors', 'integration']
task: board-polling-recovery
intent: 'No sustituir tareas por una respuesta de error y recuperar al reintentar.'
target: tools/kdd-board/public/app.js
signature: 'fetchTasks()'
test_command: 'python -m unittest tests/test_board_runtime_safety.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 250
  params_max: 5
tests: tests/test_board_runtime_safety.py
tests_sha256: 'ad1a0d516f5a471c26de4122c873cb445c32a0a29dbaca278d7c6171fc6ea6c5'
touch_only: ['tools/kdd-board/public/app.js']
deps_allowed: ['node']
forbids: ['llm']
---

## Intent
La [integracion de Board](../board-git.md) comunica errores verificables sin
confundir un fallo de lectura con una lista vacia o una tarea borrada.

## Interface
Un error HTTP, red o formato no valido mantiene la ultima lista y columnas,
muestra una causa segura y permite la siguiente lectura. Una respuesta valida
actualiza la vista y elimina el aviso de fallo recuperado.

## Invariants
Nunca tratar un objeto de error como un arreglo de tareas. No borrar ni mutar
Git al fallar una lectura. Evitar peticiones simultaneas redundantes.

## Examples
- Un 503 muestra el error del coordinador y conserva las tarjetas.
- Una respuesta posterior correcta restaura la actualizacion y limpia el aviso.

## Do / Don't
- DO: ejercitar HTTP real, errores y recuperacion con el codigo de interfaz.
- DON'T: informar una excepcion de iteracion en vez del error recibido.

## Tests
El oraculo sellado verifica el helper Node y comprueba el comportamiento con
servidor HTTP local y DOM simulado; no representa una prueba visual de navegador.

## Constraints
Conservar Ubuntu/Windows, la cobertura y las dos pasadas. PARAR y reportar si fuera
necesario alterar una proteccion remota o un oraculo previamente aprobado.
