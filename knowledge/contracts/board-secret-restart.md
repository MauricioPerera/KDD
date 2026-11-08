---
type: 'Task Contract'
title: 'Reinicio de Board con requisitos secretos persistidos'
description: 'Cargar primero las credenciales requeridas por las tareas legacy.'
tags: ['board', 'vault', 'restart', 'integration']
task: board-secret-restart
intent: 'Conservar el arranque de Board con requisitos secretos persistidos.'
target: tools/kdd-board/src/server.ts
language: typescript
signature: 'createServer(apiToken)'
test_command: 'python -m unittest tests.test_board_secret_restart'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 250
  params_max: 5
tests: tests/test_board_secret_restart.py
tests_sha256: '484211acad9f02414737bf18ee18c72f936feaebaddbd822e59cb53213548b72'
oracle_files: ['tests/test_board_secret_restart.py', 'tools/kdd-board/tests/secret-restart.test.ts', 'tools/kdd-board/tests/project-fixture.ts', 'tests/__init__.py']
touch_only: ['tools/kdd-board/src/server.ts']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
Cumplir QBR-2 del [protocolo](../quality-board-audit-remediation.md),
conservando la [aislacion del vault](board-vault-isolation.md).

## Interface
Inicializar las dependencias antes de que el constructor de TaskStore pueda
consultarlas. No cambiar las rutas HTTP, formato de tareas o esquema del vault.
El estado de un requisito secreto depende de las credenciales vigentes al cargar.

## Invariants
- Crear, satisfacer, cerrar y arrancar en otro proceso conserva una tarea valida.
- Una credencial retirada invalida el requisito en memoria y permite arrancar.
- El vault antiguo identificado se carga sin reescribir .env.local.
- Las respuestas autenticadas nunca contienen los valores sinteticos guardados.
- Leer y reiniciar no reescribe los archivos validos ni oculta errores reales.
- La copia Python sin dependencias de Board declara la aplicabilidad; la plantilla
  sin dependencias falla y no transforma el control en SKIP.

## Examples
- Requisito secreto satisfecho y credencial vigente -> arranque y GET correctos.
- Se retira la credencial entre procesos -> needs_human_input, sin corrupcion.
- Vault antiguo identificado -> reinicio valido y migracion posterior aislada.

## Do / Don't
- DO HTTP real autenticado, puertos efimeros y procesos Node distintos.
- DON'T sustituir el reinicio por dos createServer en el mismo modulo cacheado.

## Tests
El oraculo Python sella el archivo Node y ejecuta cada escenario real. El helper
crea temporales fuera de Git y limpia unicamente procesos y carpetas propios.
Conservar los 2168 IDs Python y los 86 casos Node anteriores.
El contrato conserva el perfil tradicional de los oraculos de infraestructura
de Board para declarar SKIP cuando la copia Python no instala Node. No atribuir
esa omision a aceptacion. En la plantilla, la suite instrumentada debe registrar
los tres casos Python, y cada wrapper exige un caso Node real aprobado.

## Constraints
PARAR y reportar si falta aprobacion del SHA de contratos y oraculos.
No modificar el almacenamiento, runtime, workflows, protecciones u otros oraculos.
