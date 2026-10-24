---
type: 'Task Contract'
title: 'Evidencias generadas bajo politica aprobada'
description: 'Aceptar evidencia canonica de tareas seleccionadas sin reaprobar por nombres futuros.'
tags: ['quality', 'maintenance', 'verification']
task: quality-task-evidence
intent: 'Aceptar evidencia canonica de tareas seleccionadas sin reaprobar por nombres futuros.'
target: scripts/verify_quality.py
language: python
signature: 'def approve(root, policy_path, reference):'
test_command: 'python -m unittest tests/test_generated_task_evidence.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_generated_task_evidence.py
tests_sha256: '2b11ae5bcdf921fce6d4425a8d0f471a2d7a3bfd0de96f291630c95bab05327d'
touch_only: ['scripts/verify_quality.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Politica opcional generated_task_evidence [{task_id, contract}]; runner y helpers congelados desde SHA aprobado. Comprobar diario, integridad e indice antes y despues de todos los checks.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- Tarea seleccionada done con cierre y evidencia validos -> PASS con baseline inicial.
- Archivo huerfano, otro ID, nodo alterado o helper no protegido -> rechazo antes de checks.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tests/test_generated_task_evidence.py. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
