---
type: 'Task Contract'
title: 'Contrato completo en la auditoria historica'
description: 'Recomprobar estructura e invocacion del contrato desde objetos Git sin ejecutar candidatos ni exigir ejecutables del entorno actual.'
tags: ['tasks', 'history', 'governance']
task: task-historical-controls
intent: 'Auditar los controles reconstruibles del contrato completo desde Git.'
target: scripts/validate_tasks.py
signature: 'def validate_snapshot(repo_root, ref="main") -> list:'
test_command: 'python -m unittest tests.test_task_operation_controls'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tests/test_task_operation_controls.py
tests_sha256: '67607583a8b51cd63723481d4fd37b2a93e9c91cf36a9d7443f2a93977899c75'
touch_only: ['scripts/validate_tasks.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_git', 'task_model', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent

Implementar la [lectura historica de la matriz](../operation-controls.md),
conservando el [historial](task-validation.md) y su
[perimetro](task-perimeter-history.md).

## Interface

Conservar validate_snapshot, validate_range y CLI. Usar el helper del
[coordinador](task-operation-controls.md) sin ejecutar codigo del producto.

## Invariants

- Un contrato incompleto no se vuelve valido por un checkout actual corregido.
- Recomprobar estructura e invocacion reconocida de estados distintos de
  backlog en snapshots y rangos; backlog conserva contratos en preparacion.
- Usar objetos Git; conservar refs, indice, checkout y recibos sin reescribirlos.
- No requerir que un ejecutable del pasado este instalado para auditarlo hoy.
- No afirmar que la reconstruccion prueba la disponibilidad o ejecucion pasada.
- Conservar transiciones, imports, hashes, modos regulares y origen de evidencia.

## Examples

- Ready historico sin Examples, checkout corregido -> TASK_CONTRACT.
- Ready con invocacion reconocida y ejecutable ausente hoy -> lectura valida
  sin ejecutar pruebas; intentar start ahora exige el ejecutable.

## Do / Don't

- DO reutilizar la validacion completa dentro del bundle existente.
- DON'T confiar en el checkout, pedir una rama viva o ejecutar un candidato.

## Tests

Oraculo compartido tests/test_task_operation_controls.py, congelado con su
contrato de coordinador. Preserva casos positivos de historia y producto.

## Constraints

PARAR y reportar si se necesita otro modulo confiable, editar otro oraculo,
alterar Task v1, aumentar budgets o cambiar protecciones. Requiere el helper
del coordinador y aprobacion humana del baseline antes de implementar.
