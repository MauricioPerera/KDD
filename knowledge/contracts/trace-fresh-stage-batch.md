---
type: 'Task Contract'
title: 'Agrupar lecturas frias solicitadas por la etapa de frescura'
description: 'Leer modo y contenido de los artefactos de una misma comparacion antes de publicar el lote completo.'
tags: ['traceability', 'git', 'performance', 'integration']
task: trace-fresh-stage-batch
intent: 'Reducir procesos Git en la comparacion fresca de artefactos de la tarea.'
target: scripts/traceability_git.py
signature: 'def _fresh(self, task, metadata):'
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
Reducir el coste de la [comparacion de frescura](../trace-stage-batches.md)
manteniendo [las lecturas Git frescas](trace-projection-fresh-read.md).

## Interface
Conservar _Projection._fresh y build_trace. En la etapa original de _fresh,
agrupar los pares revision/ruta frios que ella solicita mediante _read_metadata
existente. Comparar contrato, oraculo y producto con el tested_commit original.
Para tres rutas actuales frias, tres probadas retenidas y formato nativo ya
resuelto, usar como maximo un proceso Git compatible: tres actualmente.

## Invariants
- Leer modo regular y contenido de cada entrada en el mismo resultado fresco.
  No inferir modo/contenido desde el cache de task_git ni desde el checkout.
- Conservar valores ya retenidos por esta proyeccion y cache caliente sin Git.
  No compartir valores entre operaciones o repositorios.
- Agrupar exclusivamente datos que esta etapa ya pide; nunca adelantar tareas,
  historia, manifiestos ni datos de etapas posteriores. Conservar la lectura
  de evidencia y auditoria antes de _fresh y la aprobacion posterior.
- No publicar entradas parciales ante error Git o Unicode de un lote elegible.
  Mantener False ante fallo real; no convertir un error en coincidencia.
- En protocolo ausente, datos ambiguos, rutas no elegibles o refs simbolicos,
  conservar el camino serial, sus decisiones y sus comprobaciones de frescura.
- Conservar deteccion de git replace introducido al pedir esta etapa, modos
  de enlace aunque el checkout sea regular, corrupcion y recuperacion posterior.
- Mantener todos los oraculos previos, limites, workers, runtime y workflows.

## Examples
- Artefactos iguales: un lote fresco y True; producto cambiado: False.
- Enlace introducido despues de leer evidencia: False/TRACE_STALE.
- UTF-8 invalido en el ultimo contenido: False y ninguna entrada nueva del lote.

## Do / Don't
- DO usar Git real, Trace2, dos formatos nativos y el flujo completo de tarea.
- DON'T crear caches nuevas, procesos persistentes o reutilizar evidencia vieja.

## Tests
El [oraculo](../../tests/test_trace_stage_batches.py) agrega presupuesto Git real
en ambos formatos y atomicidad ante UTF-8 invalido. Los controles anteriores
de fallback, corrupcion, rutas, reemplazos tardios y reporte/CLI permanecen
intactos y se ejecutan en la regresion; no se duplican en este archivo nuevo.

## Constraints
PARAR y reportar si falta el baseline revisado o requiere otro archivo de produccion.
La mejora local no cierra el objetivo remoto de tres post-init Windows<480s.
