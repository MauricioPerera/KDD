---
type: 'Task Contract'
title: 'Instrumentar las pruebas Python del Board'
description: 'Impide que un resumen unittest inventado apruebe un archivo sin casos ejecutados.'
tags: ['ccdd', 'security', 'board']
task: board-oracle-execution
intent: 'Exigir evidencia instrumentada al verificar un oraculo Python desde el Board.'
target: tools/kdd-board/src/test-runner.ts
signature: 'export function executeTaskTest(command, cwd, secrets, oracle, timeoutMs)'
test_command: 'node --test tools/kdd-board/tests/python-oracle-proof.test.ts tools/kdd-board/tests/python-legacy-proof.test.ts'
test_runner: node-test
budget:
  cyclomatic_max: 30
  nesting_max: 6
tests: tools/kdd-board/tests/python-oracle-proof.test.ts
tests_sha256: 83499da71ea953dfb195ecf58309940e36979581fbc0569a59990d56b1d3a225
oracle_files: ['tools/kdd-board/tests/python-oracle-proof.test.ts', 'tools/kdd-board/tests/python-legacy-proof.test.ts']
touch_only: ['tools/kdd-board/src/test-runner.ts', 'scripts/board_oracle_bridge.py', 'scripts/guard_pr_baseline.py', 'tools/kdd-board/src/task-execution.ts', 'tools/kdd-board/src/types.ts', 'tools/kdd-board/src/input-validation.ts']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Aplicar [ejecucion instrumentada](../acceptance.md) a la frontera de verificacion del Board.

## Interface
Conservar la API de executeTaskTest y sus estados. El bridge confiable transmite el resultado del runner Python; no transforma stdout del oraculo en evidencia.

## Invariants
- Un resumen falso y salida temprana no cuentan como casos reales.
- Cero casos u omisiones bloquean verifiedOracle.
- Un caso real aprobado conserva PASS y un conteo positivo.
- La salida mostrada mantiene redaccion de secretos.

## Constraints
PARAR y reportar si falta el bridge o un runner soportado. El bridge y el runner instrumentado son confiables, protegidos por el gate de PR. No hay sandbox para oraculos hostiles aprobados. Los comandos historicos sin oraculo no ofrecen verifiedOracle.

## Examples
- Imprimir Ran 1 test y OK antes de os._exit(0) produce FAIL, nunca PASS.
- Una clase unittest con un caso aprobado produce PASS y passedTests=1.

## Do / Don't
DO: usar el recorder de unittest. DON'T: inferir ejecucion del texto stderr.

## Tests
El oraculo sellado cubre salida falsa seguida de exit 0, un caso real y archivos vacios o con todos los casos omitidos.
