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
tests_sha256: '36e4a445ae50468926bb3a57d88d9b8c4c2b3f7078786685c3c5108a8d7918d1'
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
- Un 503 muestra el error del coordinador y conserva las tarjetas; este control
  ya existe mediante apiFetch y se conserva con la ruta real del cliente.
- Un 200 con cuerpo que no es una lista conserva los datos y notifica el error.
- Una respuesta posterior correcta restaura la actualizacion y limpia el aviso.

## Do / Don't
- DO: ejercitar HTTP real, errores y recuperacion con el codigo de interfaz.
- DON'T: informar una excepcion de iteracion en vez del error recibido.

## Tests
El oraculo sellado verifica el helper Node y comprueba apiFetch y fetchTasks
reales con servidor HTTP local y DOM simulado; no representa una prueba visual
de navegador. La auditoria previa que omitio apiFetch no describe un 503 real.

## Constraints
Conservar Ubuntu/Windows, la cobertura y las dos pasadas. PARAR y reportar si fuera
necesario alterar una proteccion remota o un oraculo previamente aprobado.
