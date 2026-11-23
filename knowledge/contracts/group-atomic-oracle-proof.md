---
type: 'Task Contract'
title: "Garantias atomicas heredadas por los grupos"
description: "Vincular auxiliares aprobados y verificar la ejecucion instrumentada del hijo."
tags: ['audit', 'integration', 'quality']
task: group-atomic-oracle-proof
intent: "Conservar las garantias declaradas por cada hijo atomico durante la ejecucion compuesta."
target: scripts/group_contracts.py
signature: "def main()"
test_command: "python -m unittest tests.test_group_oracle_inventory"
test_runner: python-unittest
oracle_files: ["tests/test_group_oracle_inventory.py", "tests/test_group_contracts.py", "tests/test_fixture_preparation.py"]
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_group_oracle_inventory.py"
tests_sha256: '2d442bb704f93493823a6336108113e89e2aafd2105c02306eb5b773f37bd8f6'
touch_only: ["scripts/group_contracts.py"]
deps_allowed: []
forbids: ['llm']
---

## Intent
Conservar garantias de los hijos de un [grupo](../group-contracts.md).

## Interface
Proteger oracle_files y ejecutar el test_runner canonico cuando se declara.

## Invariants
Cotejar indice y archivos antes y despues de cada etapa. Conservar contencion de procesos, plazos, orden y comando historico.

## Examples
- Cambio del auxiliar bloquea ejecucion.
- Hijo omitido impide integraciones.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
Git, unittest, grupo anidado y controles de integridad y orden.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
