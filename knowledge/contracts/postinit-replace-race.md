---
type: 'Task Contract'
title: 'Trazabilidad frente a reemplazos Git durante la proyeccion'
description: 'Rechazar enlaces y cambios de historia observados durante una consulta.'
tags: ['git', 'traceability', 'integrity', 'integration']
task: postinit-replace-race
intent: 'Evitar evidencia positiva cuando git replace cambia el commit durante la auditoria.'
target: scripts/traceability_git.py
signature: 'def build_trace(repo_root, ref, manifest_path, require_verified=False):'
test_command: 'python -m unittest tests.test_postinit_replace_race'
test_runner: python-unittest
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 160
  params_max: 5
tests: tests/test_postinit_replace_race.py
tests_sha256: '09ebfbf66b4d45965b81b62db94f73c0c49d1c9bcd4d817c000e3c395c411ecf'
oracle_files: ['tests/test_postinit_replace_race.py', 'tests/test_traceability_model.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/traceability_git.py', 'scripts/task_git.py']
deps_allowed: ['stdlib', 'task_git', 'task_model', 'traceability_model', 'validate_contracts', 'validate_tasks']
forbids: ['network', 'llm']
---

## Intent
Conservar las comprobaciones historicas y de modos cuando una referencia Git
de reemplazo se modifica entre lecturas de una misma proyeccion.

## Interface
`build_trace` no debe acreditar una tarea ni su producto si un reemplazo Git
instalado durante la consulta convierte la ruta en enlace o altera su historia.

## Invariants
- Observar los modos e historial que Git devuelve en la comprobacion pertinente;
  no reutilizar una lectura anterior para aceptar el caso reemplazado.
- Rechazar el nodo enlazado con TRACE_INPUT, el producto enlazado como obsoleto
  y la historia incompatible con TRACE_JOURNAL, manteniendo los reportes previos.
- Conservar las aserciones, sellos, inventario, Ubuntu/Windows, dos pasadas y
  timeout existentes. Todo objeto y referencia del oraculo es Git real local.

## Examples
- Un task node se sustituye por un enlace despues de leer el plan: no se verifica.
- El target pasa a enlace despues de leer evidencia: se marca obsoleto.
- La historia se sustituye antes de validarla: no se acredita el diario.

## Do / Don't
- DO sincronizar los puntos de reemplazo y comprobar el modo Git realmente visto.
- DON'T tratar el SHA como prueba de invariabilidad de refs/replace.

## Tests
El oraculo hace tres sustituciones Git reales durante proyecciones independientes.

## Constraints
PARAR y reportar si se requiere cambiar un oraculo, runtime o proteccion sin la
revision exigida por `knowledge/quality-approval.md`.
