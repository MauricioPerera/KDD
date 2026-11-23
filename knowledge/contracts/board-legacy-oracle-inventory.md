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
tests_sha256: '7dc0883f1ce7c7998c22da08b6d93f4232f63d06e5f18b693f3a0a00f157cbc8'
touch_only: ["tools/kdd-board/src/task-execution.ts", "tools/kdd-board/src/test-runner.ts", "tools/kdd-board/src/input-validation.ts", "tools/kdd-board/src/types.ts"]
deps_allowed: ["node", "zod", "python"]
forbids: ['llm']
---

## Intent
Cerrar tareas JSON solo con un recibo vigente que incluya el oraculo completo. El alcance sigue [ejecucion de oraculos Board](board-oracle-execution.md).

## Interface
El flujo HTTP legacy recoge el inventario del contrato canonico y lo vincula al veredicto, junto con el target y el contrato. El cierre y recarga rechazan un recibo incompleto para ese inventario. Un contrato historico sin inventario declarado conserva su entrada principal.

## Invariants
Cada archivo declarado es regular y esta confinado a la raiz. Comparar los hashes antes y despues de la prueba y al cerrar. Conservar el modo Git, formatos de runners reconocidos y resultados FAIL, SKIP y TIMEOUT.

## Examples
- Un helper declarado intacto aparece en el recibo y permite cerrar tras PASS.
- El mismo helper cambiado invalida el cierre y se conserva el estado anterior.

## Do / Don't
- DO: reusar el punto de entrada y los controles existentes.
- DON'T: Evitar acreditar recibos parciales ni editar el oraculo anterior para lograr verde.

## Tests
Servidor HTTP y oraculo Node reales en proyecto externo a Git. Verificar hash del auxiliar, cierre estable y rechazo despues de modificarlo.

## Constraints
Aprobar el SHA del baseline antes de implementar. PARAR y reportar si se
requiere cambiar controles remotos, el runtime confiable u oraculos previos.
