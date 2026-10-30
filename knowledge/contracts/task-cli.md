---
type: 'Task Contract'
title: 'CLI de tareas versionadas'
description: 'Exponer gestion de tareas mediante una CLI local que reutiliza el modelo y diario Git.'
tags: ['ccdd', 'git', 'tasks']
task: task-cli
intent: 'Exponer gestion de tareas mediante una CLI local que reutiliza el modelo y diario Git.'
target: scripts/tasks.py
signature: 'def main(argv=None) -> int:'
test_command: 'python -m unittest tests/test_tasks_cli.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: 'tests/test_tasks_cli.py'
tests_sha256: '67a097f79a68c72c6a986328d7784f1feb3077bda981617dd7949bada814f634'
touch_only: ['scripts/tasks.py', 'README.md', 'CHANGELOG.md', '.github/workflows/validate.yml']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Exponer gestion de tareas mediante una CLI local que reutiliza el modelo y diario Git. Ver [tareas Git](../git-tasks.md) y [modelo Task](../data_models/git-task.md).

## Interface
`def main(argv=None) -> int:` es la entrada testeada; la interfaz operativa se define en el nodo canonico.

## Invariants
- Comandos create, ready, start, block, resume, finish, list, show e history.
- Mutaciones sobre main; consultas leen main incluso desde una rama de tarea.
- Opciones de aprobacion y responsable explicitas; errores legibles y exit distinto de cero.
- Salida JSON opt-in y resultados que incluyen el SHA del commit creado.
- No hay merge, push, ejecucion paralela de agentes ni segunda base de datos.

## Examples
- Crear TASK-001 y avanzar por estados permitidos produce nodos validos y commits acotados.
- Un salto backlog -> done, contrato re-sellado o indice ajeno modificado se rechaza.

## Do / Don't
- DO: usar la semantica y fronteras de confianza del modelo enlazado.
- DON'T: editar oraculos aprobados ni tratar un commit o un exit 0 vacio como aprobacion.

## Tests
Oraculo independiente en `tests/test_tasks_cli.py`, sellado antes de implementar.

## Constraints
- PARAR y reportar si cumplir exige modificar oraculos existentes o publicar cambios remotos.
- El uso de subprocess en diario/CLI/validador se limita a Git local y al runner documentado; el modelo puro no lo usa.
