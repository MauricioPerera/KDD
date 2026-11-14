---
type: 'Task Contract'
title: 'Vigencia del inventario de oráculos en trazabilidad'
description: 'Compara todos los artefactos del oráculo con la revisión probada al consultar un requisito.'
tags: ['traceability', 'git', 'oracle']
task: traceability-oracle-freshness
intent: 'Impedir que un cambio en un auxiliar del oráculo conserve la vigencia del requisito.'
target: scripts/traceability_git.py
signature: 'def build_trace(repo_root, ref, manifest_path, require_verified=False):'
test_command: 'python -m unittest tests.test_goldfish_traceability'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_goldfish_traceability.py
tests_sha256: '96a696a47be0563d02b97643302d172965bc886acf9a38ab4eb773853c3fbd3b'
oracle_files: ['tests/test_goldfish_traceability.py', 'tests/test_traceability_model.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py']
touch_only: ['scripts/traceability_git.py', 'knowledge/requirements-traceability.md']
deps_allowed: ['stdlib', 'task_git', 'task_model', 'traceability_model', 'validate_tasks', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent

La vigencia de una evidencia cerrada abarca el [inventario del oráculo](git-task-multi-oracle.md)
y la revisión probada por el cierre. Un auxiliar cambiado puede cambiar lo que las pruebas acreditan.

## Interface

Se conservan la CLI, el formato del reporte y los códigos de salida.
Un archivo inventariado distinto, ausente o no regular produce `TRACE_STALE`.

## Invariants

- Para una tarea cerrada con inventario explícito, comparar cada ruta declarada en el
  contrato de `verified_ref` entre ese commit y la revisión consultada. Conservar
  las comprobaciones de contrato, producto, evidencia y aprobación vigentes.
- Leer blobs regulares de Git en lotes acotados, con la protección de reemplazos
  del lector de inventarios de tareas. Comparar bytes exactos entre commits
  para el inventario explícito. Los atributos configurados en un checkout no
  intervienen. La normalización original al cerrar una tarea se conserva.
- Un fallo al leer cualquier entrada impide declarar vigencia. La consulta
  histórica al cierre conserva el resultado original. El checkout, el índice,
  las refs y el inventario legacy de un archivo conservan su comportamiento.

## Examples

- Cambia solo el auxiliar comprometido y su prueba falla. La consulta estricta
  de `main` devuelve `TRACE_STALE` y la consulta del cierre sigue verificada.
- Un archivo inventariado binario conserva sus bytes. Un checkout sucio o un
  cambio ajeno al inventario carece de efecto sobre la consulta histórica.

## Do / Don't

Usar objetos Git del commit exacto y reutilizar el lector del cierre de tareas.

## Tests

El oráculo cierra una tarea con Git y unittest reales y comprueba mutación,
borrado, sustitución por enlace, cambios de bytes y lecturas históricas.

## Constraints

PARAR y reportar si la solución exige relajar la verificación original de
inventario o el presupuesto del camino legacy.
