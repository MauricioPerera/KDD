---
type: 'Task Contract'
title: 'Auditoria historica del perimetro de tareas'
description: 'Reconstruir el alcance real de cierres Git sin confiar en recibos omitidos o falsificados ni ejecutar candidatos.'
tags: ['tasks', 'git', 'perimeter', 'history', 'integration']
task: task-perimeter-history
intent: 'Verificar el perimetro de los cierres historicos desde Git.'
target: scripts/validate_tasks.py
signature: 'def validate_range(repo_root, base_ref, head_ref) -> list:'
test_command: 'python -m unittest tests.test_task_perimeter_history'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tests/test_task_perimeter_history.py
tests_sha256: '15bcc1cf37ea4ba5d2ed2a5a8cbf753cfbdef6fb2666eebc3fb835e58b12fcc9'
touch_only: ['scripts/validate_tasks.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_git', 'task_model', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent

Cerrar la auditoria de KG-1 del [objetivo de gobierno](../kdd-governance-closure.md).
Complementa [el cierre](task-finish-perimeter.md) mediante el mismo criterio
de alcance y conserva las garantias del [historial](task-validation.md).

## Interface

Conservar validate_snapshot, validate_range y CLI. Leer contrato, implementacion,
integracion y evidencia como objetos Git. Usar el verificador compartido del
diario confiable, con punta inmutable del recibo y no una rama viva.

## Invariants

- Snapshot y rango rechazan TASK_PERIMETER con las rutas infractoras, aun con
  recibos omitidos, limpios falsos o una punta antigua presentada como final.
- Recalcular la historia de cambios e integracion; un cambio revertido no desaparece.
- Comparar un recibo presente con lo reconstruido y rechazar discrepancias.
- El legado sin recibo solo se acepta tras recalcular su alcance; nunca omitir
  la comprobacion ni reescribir un cierre antiguo. No afirmar verificacion pasada.
- Mantener auditoria de diario, imports, hashes, ancestros, modos regulares,
  dependencias y origen de evidencia. No usar checkout ni ejecutar candidatos.

## Examples

- Cierre antiguo valido, sin recibo -> alcance recalculado, bytes conservados.
- Cierre con outside.txt y recibo paths vacio -> TASK_PERIMETER.
- Main avanza despues del cierre o desaparece la rama viva -> el mismo
  historial valido se conserva por sus objetos Git inmutables.

## Do / Don't

- DO leer el contrato aprobado y usar el mismo control del cierre.
- DON'T deducir alcance de mensajes de commit, archivos del checkout, listas
  declaradas por el candidato o nombres de rama que puedan moverse.

## Tests

Oraculo nuevo en tests/test_task_perimeter_history.py; importa el fixture
nuevo de tests/test_task_finish_perimeter.py y construye cierres historicos
con oraculos reales ejecutados. Todos los repos y aprobaciones son sinteticos.
La lectura historica no debe lanzar pruebas ni cambiar ningun artefacto.

## Constraints

PARAR y reportar si hace falta ampliar el bundle confiable, editar otro oraculo,
cambiar Task v1 o debilitar las transiciones vigentes. Solo Git local; sin red.
El contrato de cierre debe estar implementado antes de completar esta tarea.
