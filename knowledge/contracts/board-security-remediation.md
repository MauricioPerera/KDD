---
type: 'Task Contract'
title: 'Remediación de seguridad y WebMCP del tablero'
description: 'Restringe el vault local, registra herramientas WebMCP en el navegador y codifica identificadores de UI.'
tags: ['ccdd', 'security', 'webmcp', 'kdd-board']
task: board-security-remediation
intent: 'Corregir hallazgos auditados del KDD-Board sin ampliar sus privilegios ni exponer secretos.'
target: tools/kdd-board/src/blind-vault.ts
language: typescript
signature: 'setSecret(key, secretValue)'
test_command: 'node --test tools/kdd-board/tests/security-remediation.test.ts'
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: 'tools/kdd-board/tests/security-remediation.test.ts'
tests_sha256: 'bbb6e667686a5e7a85185c5cbec5693bc4950a5e651490e4f6c32461a522f8fa'
touch_only: ['tools/kdd-board/src/blind-vault.ts', 'tools/kdd-board/public/app.js', 'tools/kdd-board/public/index.html', 'tools/kdd-board/DEFINITION.md', 'README.md', 'scripts/run_board.sh', 'scripts/run_board.ps1', 'knowledge/contracts/board-security-remediation.md', 'knowledge/index.md']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent

Aplicar los límites de [validación](../validacion.md) y las garantías de
[verificación](../verification-guarantees.md) a la superficie de KDD-Board.

## Interface

El vault persiste secretos solo en archivos propietarios; el navegador registra
las tools WebMCP con los esquemas publicados por el servidor.

## Invariants

- Un listado del vault no revela fragmentos ni longitud de un secreto.
- El archivo nuevo del vault es `0600` en POSIX.
- Solo el navegador registra tools con `document.modelContext` disponible.
- Identificadores de archivos o tareas no se interpolan como código JavaScript.

## Examples

- Un secreto `super-secret-value-12345` se lista como `***`.
- Un navegador con WebMCP recibe las ocho tools declaradas.

## Do / Don't

- DO: reutilizar los esquemas HTTP existentes y requerir el token local en cada acción.
- DON'T: registrar WebMCP desde el proceso Node ni prometer aislamiento del código de prueba.

## Tests

El oráculo verifica permisos POSIX, enmascarado, registro de las ocho tools y
codificación segura de argumentos.

## Constraints

- PARAR y reportar si la solución requiere publicar el servicio fuera de loopback.
