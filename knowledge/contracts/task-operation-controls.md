---
type: 'Task Contract'
title: 'Controles completos antes de operar tareas'
description: 'Repetir contrato completo y soporte del runner en las operaciones del coordinador, sin ejecutar pruebas al preparar o iniciar.'
tags: ['tasks', 'governance', 'verification']
task: task-operation-controls
intent: 'Aplicar la matriz obligatoria de controles en el coordinador de tareas.'
target: scripts/task_git.py
signature: 'def mutate(repo_root, operation, task_id, options) -> dict:'
test_command: 'python -m unittest tests.test_task_operation_controls'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_task_operation_controls.py
tests_sha256: '67607583a8b51cd63723481d4fd37b2a93e9c91cf36a9d7443f2a93977899c75'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts', 'validate_tasks']
forbids: ['network', 'llm']
---

## Intent

Implementar la [matriz de controles](../operation-controls.md), conservando el
[diario](task-journal.md), el [perimetro de cierre](task-finish-perimeter.md)
y la [aprobacion independiente](../quality-approval.md).

## Interface

Conservar mutate y CLI. Reutilizar el validador completo de contratos y el
reconocimiento de invocaciones existente. El helper historico sigue viviendo
dentro de task_git.py y del bundle de cinco modulos.

## Invariants

- ready, start y finish validan el contrato completo contra la aprobacion.
- Invocacion no soportada o ejecutable no disponible -> TASK_RUNNER antes
  de publicar estado, rama o evidencia; nunca ejecutar un oraculo al preparar/iniciar.
- Contrato estructuralmente incompleto -> TASK_CONTRACT antes del oraculo.
- Conservar controles de integracion, perimetro, dependencias y artefactos.
- CLI y API Python no permiten omitir ninguno de los controles requeridos.
- Mantener los presupuestos mas estrictos existentes, sin cambiar otro oraculo.

## Examples

- pytest no soportado o ejecutable python3.9999 ausente -> ready rechazado.
- unittest y Node reconocidos/disponibles -> ready/start sin ejecutar pruebas.
- Contrato antiguo sin Examples -> no iniciar ni cerrar trabajo con ese contrato.

## Do / Don't

- DO usar validacion completa y artefactos Git comprobados.
- DON'T aprobar un subconjunto de metadata o ejecutar pruebas para comprobar
  si se puede iniciar la tarea.

## Tests

Oraculo nuevo tests/test_task_operation_controls.py. Reutiliza fixtures reales
congelados de test_generated_task_evidence y test_task_finish_perimeter sin
modificarlos. Incluye regresiones de producto como controles positivos del
runner de calidad actual; no autoriza cambiar verify_quality.py.

## Constraints

PARAR y reportar si hace falta otra fuente, ampliar el bundle confiable,
subir un budget o editar un oraculo anterior. No implementar antes de la
aprobacion humana del baseline; conservar Ubuntu/Windows y dos pasadas.
