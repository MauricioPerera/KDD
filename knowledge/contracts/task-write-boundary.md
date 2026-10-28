---
type: 'Task Contract'
title: 'Frontera fisica de escritura del diario de tareas'
description: 'Rechazar destinos enlazados antes de pruebas y commits sin modificar canarios ni estados.'
tags: ['tasks', 'security', 'integration']
task: task-write-boundary
intent: 'Impedir escrituras externas del coordinador por aliases de archivos gestionados.'
target: scripts/task_git.py
language: python
signature: 'def mutate(repo_root, operation, task_id, options):'
test_command: 'python -m unittest tests/test_task_write_boundary.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 180
  params_max: 5
tests: tests/test_task_write_boundary.py
tests_sha256: '839a3b6fbec30b3d9c1b9e1398cd1a27a12c0aab7d5afe44d5cd1eac81676425'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_model', 'task_evidence', 'validate_contracts']
forbids: ['network', 'llm']
---
## Intent
Aplicar la [frontera y limites](../task-quality-fixture-remediation.md).
## Interface
Conservar API/CLI y formato del diario. Una ruta gestionada insegura produce
TASK_PATH antes del oraculo, rama, respaldo o escritura. Board propaga ese error.
## Invariants
Comprobar ancestros y destinos con lstat; rechazar symlinks/reparse, archivos
especiales y destinos con varios hardlinks. Preservar HEAD, indice, refs y
canarios ante rechazo. Conservar rollback y las transiciones existentes.
## Examples
- Nodo con hardlink externo: ready falla y conserva ambos nombres intactos.
- Flujo ordinario: cierre con tests reales y commits acotados validos.
## Do / Don't
- DO usar Git, filesystem, CLI y backend Board reales en ambos OS.
- DON'T prometer sandbox ni convertir un timeout en rechazo de ruta demostrado.
## Tests
Oraculo nuevo independiente: canarios, estados, locks, rollback real y Node.
## Constraints
PARAR y reportar si requiere cambiar otro oraculo, runtime o proteccion.
