---
type: 'Task Contract'
title: 'Catalogo de contratos al iniciar'
description: 'Cargar los contratos antes de crear tareas en el tablero.'
tags: ['ccdd', 'security']
task: catalog-startup
intent: 'Cargar el catalogo de contratos al iniciar el tablero.'
target: tools/kdd-board/public/app.js
language: javascript
signature: 'loadContractCatalog()'
test_command: 'node --test tools/kdd-board/tests/catalog-startup.test.ts'
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: 'tools/kdd-board/tests/catalog-startup.test.ts'
tests_sha256: '9d529c4076fe896c686d8c41b017276360f0c798771d90d9792765e6ea525e58'
touch_only: ['tools/kdd-board/public/app.js']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
Aplicar la [validacion](../validacion.md) a la evidencia local del tablero.

## Interface
`loadContractCatalog()` carga el catalogo compartido.

## Invariants
- Crear una tarea no requiere visitar documentacion previamente.
- El polling de tareas no repite una carga de catalogo exitosa.

## Examples
- Inicio con contrato existente -> opcion disponible al crear tarea.
- Segundo polling -> reutiliza el catalogo.

## Do / Don't
- DO: mantener el escape de texto en opciones HTML.
- DON'T: vaciar una seleccion existente al refrescar.

## Tests
Regresion de arranque con DOM minimo y verificacion real en navegador.

## Constraints
- PARAR y reportar si la API no devuelve un catalogo valido.
