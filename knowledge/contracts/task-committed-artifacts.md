---
type: 'Task Contract'
title: 'Validar metadatos de tareas desde archivos regulares de Git'
description: 'Separar lecturas historicas del checkout conservando aprobacion, modos Git y fronteras del coordinador.'
tags: ['tasks', 'git', 'history', 'integration']
task: task-committed-artifacts
intent: 'Validar snapshots y rangos sin consumir rutas fisicas del checkout actual.'
target: scripts/task_git.py
language: python
signature: 'def contract_metadata(root, data, revision, *, committed_only=False):'
test_command: 'python -m unittest tests/test_task_committed_artifacts.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tests/test_task_committed_artifacts.py
tests_sha256: '944939286c2a0e177d02b841e5e837eec65c08ed878e370d062e99ff96461915'
touch_only: ['scripts/task_git.py', 'scripts/validate_tasks.py']
deps_allowed: ['stdlib', 'task_model', 'task_evidence', 'task_git', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent

Aplicar la [frontera versionada](../review-p2-remediation.md) al
[diario](../git-tasks.md) y la [proyeccion](../requirements-traceability.md).

## Interface

Opcion interna committed_only, desactivada por defecto. validate_snapshot y
validate_range la usan al leer metadatos desde Git. Sus firmas y las de la CLI
y build_trace se conservan. Las mutaciones siguen con la proteccion fisica.

## Invariants

- Leer las revisiones resueltas y exigir archivos regulares Git.
- Conservar aprobacion explicita, sello, cierre y todas las transiciones.
- Rechazar rutas de escape, archivos Git ausentes y modo 120000, aunque el checkout sea valido.
- Ignorar aliases, ausencias y cambios del checkout al consultar historia.
- Conservar safe_path, main limpio y lock para las mutaciones.
- No ejecutar producto/oraculos, materializar checkout o escribir para consultar.

## Examples

- main valido con src convertido localmente en junction externa: mismo reporte.
- Otra rama con enlace Git: main historico sigue siendo consultable.
- Snapshot ready con target 120000 y payload Python valido: rechazo.
- Evidencia adulterada y checkout enlazado: conservar el error de evidencia.

## Do / Don't

- DO: reutilizar el validador canonico y la cache de objetos inmutables.
- DON'T: desactivar auditoria, seguir enlaces Git o relajar el modo de escritura.

## Tests

tests/test_task_committed_artifacts.py completa una tarea real y usa el fixture
sellado por traceability-model, aliases nativos, canarios, indice Git y procesos
de CLI. No hay mocks de Git, del coordinador o del sistema de archivos.

## Constraints

Este contrato autoriza los dos modulos canonicos indicados; no el modelo Task,
workflows o runtime. PARAR y reportar si se necesita un oraculo no revisado
o una proteccion remota.
