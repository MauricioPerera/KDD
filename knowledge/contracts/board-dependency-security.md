---
type: 'Task Contract'
title: 'Dependencias seguras de KDD Board'
description: 'Elevar Zod corregido y probar el runtime real y el lock compatible.'
tags: ['quality', 'maintenance', 'verification']
task: board-dependency-security
intent: 'Elevar Zod corregido y probar el runtime real y el lock compatible.'
target: tools/kdd-board/package.json
language: json
signature: 'dependencies(zod)'
test_command: 'python -m unittest tests/test_board_dependencies.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_board_dependencies.py
tests_sha256: 'b0876283e2dfc20d61f966510a3c600a5c8d1f1c21fa1061d5a2f0d9648e7833'
touch_only: ['tools/kdd-board/package.json', 'tools/kdd-board/package-lock.json']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Manifest y lock seleccionan Zod >=4.6.6 <5; instalacion reproducible sin scripts de lifecycle. Version instalada coincide con el lock y fastwebmcp sigue operable.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- Instalacion parcheada -> schema funcional y entrada excesiva rechazada sin abortar.
- Lock vulnerable o runtime diferente -> fallo verificable.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tests/test_board_dependencies.py. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
