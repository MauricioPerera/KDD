---
type: 'Task Contract'
title: 'Probar la cadena integrada en su etapa original'
description: 'Agrupar dos relaciones positivas y sus identidades sin anticipar datos de otras etapas.'
tags: ['git', 'tasks', 'evidence', 'performance']
task: task-evidence-chain-proof
intent: 'Reducir procesos de la cadena base tip tested de una tarea.'
target: scripts/validate_tasks.py
signature: 'def _proof_refs(root, task, report):'
test_command: 'python -m unittest tests.test_task_proof_batches'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_task_proof_batches.py
tests_sha256: '96dc769a8939864a052e491834a101aa492a71035bd705d41159753b7f71cb96'
oracle_files: ['tests/test_task_proof_batches.py', 'tests/test_task_history_read_cost.py', 'tests/test_traceability_model.py', 'tests/test_task_git.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py', 'scripts/validate_tasks.py']
deps_allowed: ['stdlib', 'task_git', 'task_model', 'task_evidence', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Reducir el [coste del post-init](../postinit-proof-cost.md) manteniendo la
[evidencia real](task-journal.md) y el [perimetro](task-finish-perimeter.md).

## Interface
Conservar _proof_refs, task_perimeter, _finish, mutate y las interfaces publicas.
Para una cadena nativa fria de tres commits distintos y formato ya resuelto,
probar base -> tip -> tested y sus identidades en como maximo un proceso Git,
incluida la posterior comprobacion de esas identidades por _perimeter_refs:
cinco procesos actualmente. La auditoria completa de la tarea del oraculo
usa como maximo 48 procesos: 53 actualmente; el limite previo de 62 no cambia.

## Invariants
- Agrupar solo las dos relaciones que _proof_refs o _finish ya solicitan.
  Mantener el primer error y el cortocircuito de tip igual a base en finish.
  No adelantar lectura de nodos, contrato, producto, evidencia ni manifiesto.
- Conservar la cache y las decisiones anteriores para pares ya calientes.
  Solo una prueba positiva completa permite publicar los dos pares y los
  endpoints que aparecen como commits realmente leidos; nunca padres crudos.
- El recorrido auxiliar, si se usa, declara --max-count=2048 y conserva
  ambos padres y fronteras relevantes. No sustituye el recorrido completo
  del diario ni permite inferir False de una ventana parcial.
- Entrada simbolica o no canonica, protocolo no soportado, objeto ausente,
  error, datos ambiguos o falta de prueba completa conservan el camino
  serial original. No publicar parcialmente ni cachear rechazos.
- Conservar rechazo de historia adulterada, merges ajenos, identidades
  peladas y reemplazos; descartar la cache al salir de la operacion. Mantener
  el aislamiento por repositorio y la recuperacion tras reponer un objeto.
- Mantener los oraculos, presupuestos de complejidad, workers, timeouts,
  Ubuntu/Windows y ambas suites. No crear procesos o caches persistentes.

## Examples
- Una cadena A -> B -> merge(B,C) se prueba junta; C -> B sigue fallando.
- Un tag de B no queda certificado como commit al probar su ascendencia.
- Una cadena valida que supera 2.048 commits conserva su resultado por fallback.

## Do / Don't
- DO usar Git real, Trace2 y una tarea cerrada con evidencia de producto real.
- DON'T reutilizar resultados de validacion ni omitir commits intermedios.

## Tests
El [oraculo](../../tests/test_task_proof_batches.py) verifica presupuestos,
ramas divergentes, tags, reemplazos, objetos recuperados y ventana incompleta.
La integracion completa conserva diario, refs, recibo y trazabilidad. Los
oraculos previos de modos, historia y escritura se conservan intactos.

## Constraints
PARAR y reportar si falta el baseline revisado o se requiere otro target,
runtime, workflow, cambio de presupuesto anterior o proteccion remota.
El ahorro local no cierra las tres mediciones completas exigidas por el objetivo.
