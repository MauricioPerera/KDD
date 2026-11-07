---
type: 'Task Contract'
title: 'Agrupar contenidos del par de contrato en su etapa original'
description: 'Leer oraculo y producto en un lote Git despues de comprobar conjuntamente sus modos.'
tags: ['traceability', 'git', 'performance', 'integration']
task: trace-contract-content-batch
intent: 'Reducir un proceso Git en cada par frio de contenidos del contrato.'
target: scripts/traceability_git.py
signature: 'def _contract_inputs(self, revision, oracle, target):'
test_command: 'python -m unittest tests.test_trace_stage_batches'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_trace_stage_batches.py
tests_sha256: '3f000c0c2c8b53c05119820f74079da64ce35dd517666536329d738ef8f44401'
oracle_files: ['tests/test_trace_stage_batches.py', 'tests/test_trace_projection_fresh_read.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/traceability_git.py']
deps_allowed: ['stdlib', 'task_git', 'task_model', 'traceability_model', 'task_evidence', 'validate_tasks', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Reducir procesos de la [etapa de contrato](../trace-stage-batches.md) sin
debilitar [las comprobaciones de rutas](traceability-contract-path-batch.md).

## Interface
Conservar _Projection._contract_inputs y build_trace. Para dos rutas frias,
distintas, exactas y sin solapamiento en un OID nativo, conservar una consulta
ls-tree de modos y obtener los dos blobs con journal.blobs existente.
Maximo dos procesos Git despues de resolver el formato nativo: tres actualmente.

## Invariants
- Mantener valores normalizados, orden del par y errores del camino serial.
- Mantener el rechazo de ausencia, enlace, arbol, submodulo y ruta no exacta.
- Para cache parcial, rutas solapadas o revision no nativa, conservar el
  camino serial y sus valores previos; cache completamente caliente no lanza Git.
- No publicar parcialmente contenidos nuevos cuando el lote de blobs falla.
- No cambiar etapas, preleer otros artefactos, usar checkout, ejecutar producto,
  modificar refs/indice ni sustituir observaciones frescas por pruebas antiguas.
- Conservar los [limites de lectura](postinit-git-object-reads.md), las
  [lecturas frescas](trace-projection-fresh-read.md) y todos los oraculos previos.

## Examples
- Oraculo y target regulares: una consulta de modos y un lote de dos blobs.
- Ruta ausente y enlace: mismo primer error que dos lecturas individuales.
- Oracle ya retenido: preservar su valor y leer solo el target solicitado.

## Do / Don't
- DO medir Git real mediante Trace2 en SHA-1 y SHA-256 y comparar con el serial.
- DON'T cambiar runtime, workflows, limites, workers ni pruebas existentes.

## Tests
El [oraculo](../../tests/test_trace_stage_batches.py) agrega el presupuesto de
procesos con Git real, Unicode y vacios en ambos formatos. Los oraculos previos
de rutas agrupadas, lecturas frescas, reemplazos y tareas cerradas se conservan
intactos y verifican los demas controles en la regresion.

## Constraints
PARAR y reportar si falta el baseline revisado o requiere ampliar touch_only.
No declarar el objetivo cumplido antes de las tres muestras remotas completas.
