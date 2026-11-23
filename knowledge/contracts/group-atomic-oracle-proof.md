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
Conservar las garantias declaradas por cada hijo atomico durante la ejecucion compuesta. El alcance sigue [contratos de grupo](../group-contracts.md).

## Interface
La CLI de grupos incluye cada oracle_files declarado en sus archivos aprobados. Despacha los hijos que declaran test_runner por el ejecutor instrumentado canonico. El hijo historico sin test_runner conserva el comando vigente.

## Invariants
Cotejar indice y copia de trabajo antes de cualquier ejecucion y despues de cada etapa. Conservar orden del grafo, deduplicacion, timeout, identidad aprobada y ausencia de integraciones posteriores a un hijo inconcluso.

## Examples
- Un auxiliar del hijo que difiere del aprobado bloquea el grupo antes de ejecutar.
- Todos los casos del hijo omitidos bloquean las integraciones siguientes.

## Do / Don't
- DO: reusar el punto de entrada y los controles existentes.
- DON'T: Evitar inferir casos ejecutados a partir del codigo de salida generico.

## Tests
Grupos anidados y un hijo compartido con Git y unittest reales. Cubrir deriva antes y despues de una etapa, omision total y camino positivo con orden exacto.

## Constraints
Aprobar el SHA del baseline antes de implementar. PARAR y reportar si se
requiere cambiar controles remotos, el runtime confiable u oraculos previos.
