---
type: 'Task Contract'
title: 'Aislar el vault de la configuracion del proyecto'
description: 'Evitar modificaciones accidentales del archivo dotenv de la aplicacion.'
tags: ['board', 'vault', 'integration']
task: board-vault-isolation
intent: 'Guardar secretos del tablero sin modificar la configuracion ajena.'
target: tools/kdd-board/src/server.ts
language: typescript
signature: 'createServer(apiToken)'
test_command: 'python -m unittest tests/test_board_runtime_safety.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 250
  params_max: 5
tests: tests/test_board_runtime_safety.py
tests_sha256: '36e4a445ae50468926bb3a57d88d9b8c4c2b3f7078786685c3c5108a8d7918d1'
touch_only: ['tools/kdd-board/src/server.ts', 'tools/kdd-board/src/blind-vault.ts']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
El [vault de Board](board-security-remediation.md) no es propietario de la
configuracion dotenv de una aplicacion. No debe reescribirla ni exponerla como
credenciales del tablero.

## Interface
Guardar las credenciales del tablero en `.kdd-board/vault.env`. Cuando no exista
el archivo dedicado, admitir datos anteriores unicamente si `.env.local` lleva
la cabecera exacta que identificaba al vault; conservar ese archivo intacto y
adoptar sus credenciales al primer cambio. Un dotenv ordinario nunca se importa.

## Invariants
Lectura, creacion, cambio, borrado y reinicio dejan `.env.local` intacto byte a
byte. El archivo dedicado tiene los permisos y la exclusion Git del vault;
un conflicto o fallo de escritura no descarta datos. Los valores nunca aparecen
en las respuestas publicas; codigo de pruebas ejecutado no queda aislado.
En un repositorio Git, si la ruta no esta excluida o ya esta en el indice,
rechazar la modificacion antes de escribir con un error accionable; no editar
automaticamente `.gitignore`, el indice ni el historial. Una exclusion valida
permite guardar sin que el archivo aparezca en `git status`.

## Examples
- Un dotenv multilínea con comentarios sigue identico tras guardar y borrar.
- Un vault previo identificado conserva credenciales durante la migracion.
- Un Git sin exclusion o con el vault ya versionado rechaza guardar.

## Do / Don't
- DO: pruebas HTTP autenticadas, reinicio y archivos reales temporales.
- DON'T: importar un dotenv arbitrario ni borrar el archivo previo.

## Tests
El oraculo Python verifica el hash del helper Node, que ejecuta los escenarios
HTTP y de archivos reales. Una copia Python inicializada sin dependencias de
Board declara la omision de aplicabilidad, como las integraciones existentes.

## Constraints
Conservar Ubuntu/Windows, la cobertura y las dos pasadas. PARAR y reportar si fuera
necesario alterar una proteccion remota o un oraculo previamente aprobado.
