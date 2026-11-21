---
type: 'Task Contract'
title: 'Semillas privadas de tareas Git'
description: 'Reusar preparacion con Git por caso aislado.'
tags: ['ci', 'fixtures', 'git', 'performance']
task: task-fixture-stage-reuse
intent: 'Reducir la preparacion repetida de los oraculos de tareas.'
target: tests/test_git_task_multi_oracle.py
signature: 'class GitTaskMultiOracle(unittest.TestCase):'
test_command: 'python -m unittest tests.test_task_fixture_stage_reuse'
test_runner: python-unittest
test_scope: infrastructure
tests: tests/test_task_fixture_stage_reuse.py
tests_sha256: 'a452ce67078bba8d68ada1c48101377bfb1400a83aee7b7232f498aea4795058'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 6
oracle_files: ['tests/test_task_fixture_stage_reuse.py', 'tests/__init__.py']
touch_only: ['tests/test_git_task_multi_oracle.py', 'knowledge/contracts/git-task-multi-oracle.md', 'knowledge/contracts/quality-git-task-multi-oracle.md']
deps_allowed: ['stdlib', 'git', 'test_generated_task_evidence']
forbids: ['network', 'llm']
---

## Intent
Reducir setup repetido de los [oraculos multiarchivo](git-task-multi-oracle.md)
y las [lecturas Git](task-transition-read-cost.md).

## Interface
`project(...)` conserva sus opciones y reusa la base por formato.
`integrated_project()` entrega el escenario integrado predeterminado
para tres controles del cierre: resultado Python, deriva y recibo.

## Invariants
- Una preparacion real por fase, formato y proceso, entre instancias.
  Una copia modificada no contamina una copia posterior ni la semilla.
  No compartir indice, config, refs, objetos, enlaces ni resultados.
- Conservar SHA-1 y SHA-256. Aplicar las opciones y cambios de cada caso
  despues de copiar la base. Los casos que prueban ready siguen usando ready real.
- El escenario integrado usa la variante predeterminada. Cada cierre
  ejecuta sus oraculos reales y genera evidencia propia.
- Preservar los 2611 IDs, Ubuntu y Windows, dos pasadas, cobertura en la
  primera y el [plazo de post-init](postinit-windows-common-deadline.md).

## Examples
- Dos casos reciben el mismo commit de partida y confirman cambios privados.
- El cambio del oraculo secundario solo pertenece al caso que lo solicita.

## Do / Don't
Medir el costo completo con Git real. Usar copias fisicas independientes.

## Tests
Git y Trace2 cotejan init por formato, ramas, objetos y aislamiento.
Crear otra copia despues de mutar y limpiar la primera y cerrar la segunda.
Los controles previos cubren variantes y cierres reales.

## Constraints
PARAR y reportar si falta revisar un oraculo congelado. Acreditar el ahorro
neto con tres CI del mismo SHA. Los contratos existentes del perimetro
solo actualizan sus sellos. Revisar tambien los inventarios de
[snapshots](task-oracle-snapshot-batch.md) y [lecturas](task-transition-read-cost.md).
