---
type: 'Task Contract'
title: 'Validador de transiciones Git'
description: 'Auditar snapshots y transiciones de tareas en la linea principal de Git sin ejecutar candidatos.'
tags: ['ccdd', 'git', 'tasks']
task: task-validation
intent: 'Auditar snapshots y transiciones de tareas en la linea principal de Git sin ejecutar candidatos.'
target: scripts/validate_tasks.py
signature: 'def validate_range(repo_root, base_ref, head_ref) -> list:'
test_command: 'python -m unittest tests/test_validate_tasks.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tests/test_validate_tasks.py'
tests_sha256: '628fdde0600bf54fd877bb7d5c7bef593ea672de9e807c8bcb7d20b68cc557a0'
touch_only: ['scripts/validate_tasks.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Auditar snapshots y transiciones de tareas en la linea principal de Git sin ejecutar candidatos. Ver [tareas Git](../git-tasks.md) y [modelo Task](../data_models/git-task.md).

## Interface
`def validate_range(repo_root, base_ref, head_ref) -> list:` es la entrada testeada; la interfaz operativa se define en el nodo canonico.

## Invariants
- Lee blobs Git, no archivos del checkout; ausencia de tareas es opcional.
- Comprueba modelo, enlaces de contratos, dependencias y pruebas de cierre.
- Un rango audita cada commit de primera linea, no solo diferencia neta, y rechaza bajas de tareas.
- El cierre requiere un commit exclusivo de nodo y evidencia con tested_commit igual al padre.
- Un mensaje de commit no sustituye cambios y evidencia validos; no ejecuta test_command.

## Examples
- Crear TASK-001 y avanzar por estados permitidos produce nodos validos y commits acotados.
- Un salto backlog -> done, contrato re-sellado o indice ajeno modificado se rechaza.

## Do / Don't
- DO: usar la semantica y fronteras de confianza del modelo enlazado.
- DON'T: editar oraculos aprobados ni tratar un commit o un exit 0 vacio como aprobacion.

## Tests
Oraculo independiente en `tests/test_validate_tasks.py`, sellado antes de implementar.

## Constraints
- PARAR y reportar si cumplir exige modificar oraculos existentes o publicar cambios remotos.
- El uso de subprocess en diario/CLI/validador se limita a Git local y al runner documentado; el modelo puro no lo usa.
