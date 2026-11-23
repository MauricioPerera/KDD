---
type: 'Task Contract'
title: "Evidencia completa del oraculo de Board legacy"
description: "Vincular el inventario de la prueba al resultado y rechazar una transicion con evidencia caducada."
tags: ['audit', 'integration', 'quality']
task: board-legacy-oracle-inventory
intent: "Cerrar tareas JSON solo con un recibo vigente que incluya el oraculo completo."
target: tools/kdd-board/src/task-execution.ts
language: typescript
signature: "export async function runTaskTests(store, vault, projectDir, id)"
test_command: "node --test tools/kdd-board/tests/legacy-oracle-inventory.test.ts"
test_runner: node-test
oracle_files: ["tools/kdd-board/tests/legacy-oracle-inventory.test.ts", "tools/kdd-board/tests/project-fixture.ts", "tools/kdd-board/package-lock.json"]
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tools/kdd-board/tests/legacy-oracle-inventory.test.ts"
tests_sha256: '4b40c4248f2f9a4e4d7db2d3f12a331627d97505ce46cbcc57e3db0fa16c42e8'
touch_only: ["tools/kdd-board/src/task-execution.ts", "tools/kdd-board/src/test-runner.ts", "tools/kdd-board/src/input-validation.ts", "tools/kdd-board/src/types.ts"]
deps_allowed: ["node", "zod", "python"]
forbids: ['llm']
---

## Intent
Cerrar solo con el [oraculo completo](board-oracle-execution.md).

## Interface
El recibo vincula contrato, target y archivos declarados al runner.

## Invariants
Validar confinamiento y hashes antes, despues y al cerrar o recargar. Recibo parcial de un inventario exige rerun. Modo Git intacto.

## Examples
- Auxiliar intacto aparece en el recibo y permite cerrar.
- Cambio del auxiliar o recibo parcial impide cerrar.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
Board HTTP, Node, cambio real y recarga de almacenamiento.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
