---
type: 'Task Contract'
title: 'Probar identidad aprobada y ascendencia con una respuesta Git'
description: 'Evitar una resolucion de commit repetida sin admitir alias o identidades peladas como baseline.'
tags: ['git', 'approval', 'performance', 'integration']
task: task-approval-ancestor-proof
intent: 'Reducir procesos de la comprobacion del baseline aprobado.'
target: scripts/task_git.py
signature: 'def _require_approved_ancestor(root, approved, revision):'
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
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_model', 'task_evidence', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Reducir las comprobaciones repetidas identificadas en el
[perfil de post-init](../postinit-proof-cost.md), conservando la
[identidad aprobada](task-approval-identity.md).

## Interface
Conservar _require_approved_ancestor y contract_metadata, las operaciones y la
CLI. Un baseline canonico valido con el formato ya conocido y prueba fria usa
como maximo un proceso Git: dos actualmente. Conservar TASK_APPROVAL ante un
baseline invalido y la comprobacion explicita de identidad completa.

## Invariants
- Probar que approved es exactamente el OID canonico de un commit y ancestro
  de revision. Un tag pelado, alias, abreviacion, arbol, blob, rama hexadecimal
  de otra longitud, objeto ausente o ancestro ajeno sigue rechazado.
- La salida canonica de Git puede probar ambas propiedades; una coincidencia
  de nombres, un padre impreso o la longitud de una entrada no las prueban.
- Conservar la cache positiva existente por operacion y repositorio. No
  guardar fallos, inferir el algoritmo desde un nombre ni cachear refs moviles.
- No aprobar un resultado incompleto, ambiguo o un error Git. Conservar las
  comprobaciones frescas de las etapas posteriores y todas las validaciones
  de contrato, oraculo, evidencia, historial y perimetro.
- No modificar oraculos previos, sus limites, el runtime ni los workflows.

## Examples
- Un SHA-1/SHA-256 canonico y ancestro mantiene la aprobacion con una consulta.
- El OID de un tag anotado no equivale al OID del commit que el tag senala.
- Un baseline ausente falla; escribir el objeto y repetir exige otra prueba.

## Do / Don't
- DO medir con Git real y Trace2 en ambos formatos nativos.
- DON'T convertir un resultado de nombre simbolico en una identidad aprobada.

## Tests
El [oraculo nuevo](../../tests/test_task_proof_batches.py) agrega el presupuesto
y el flujo real completo. Reutiliza sin cambios los controles previos de
identidad, formatos, reemplazos, historia y escritura; no los duplica.

## Constraints
PARAR y reportar si falta el baseline revisado o se requiere ampliar touch_only.
El objetivo remoto y sus tres mediciones siguen el protocolo enlazado.
