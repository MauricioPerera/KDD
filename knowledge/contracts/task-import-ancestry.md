---
type: 'Task Contract'
title: 'Auditoria de importaciones con base integrada'
description: 'Auditar merges anidados cuando la base publica entra por un padre secundario sin perder historial.'
tags: ['git', 'tasks', 'history', 'ci']
task: task-import-ancestry
intent: 'Aceptar una importacion legitima con main integrado y seguir rechazando transiciones ocultas.'
target: scripts/validate_tasks.py
signature: 'def validate_range(repo_root, base_ref, head_ref) -> list:'
test_command: 'python -m unittest tests.test_task_import_ancestry'
budget:
  cyclomatic_max: 12
  nesting_max: 5
  lines_max: 100
  params_max: 5
tests: tests/test_task_import_ancestry.py
tests_sha256: 'a7c55da16dd3a58b3343f12e31b495026a3ff04f8afea7a4aedd839dea6c8224'
touch_only: ['scripts/validate_tasks.py']
deps_allowed: ['stdlib', 'task_git', 'task_model', 'git']
forbids: ['network', 'llm']
---

## Intent
Conservar el contrato de [publicacion](task-publication.md) al auditar merges
anidados donde la rama fuente ya integro la base por otro padre.

## Interface
`validate_range` y CLI conservan las mismas firmas, resultados y limites.

## Invariants
- La base publica de la llamada externa permanece en la cadena de primeros
  padres del head; una base ajena o que solo sea padre secundario se rechaza.
- Para una importacion interna, si la base de integracion es ancestro real de
  la fuente pero no pertenece a su cadena de primeros padres, auditar desde
  un ancestro comun verificable de ambas historias que si pertenezca a esa
  cadena, sin omitir commits ni transiciones de ninguno de los lados.
- Los merges anidados siguen comprobando integridad y procedencia; una
  transicion ilegal seguida de restauracion falla aunque el estado final sea
  valido. Un conflicto de tarea o una modificacion del merge sigue fallando.
- No ejecutar codigo del repositorio candidato ni modificar refs, indice o
  arbol. Ante historia incompleta, ancestro ambiguo o Git fallido, fallar.
- No alterar workflows, protecciones, runtime, oraculos previos o limites.

## Examples
- Rama incorpora main como segundo padre y luego se publica: auditar toda su
  historia, aceptar si todas sus transiciones son validas.
- Transicion falsa anterior o posterior al merge, seguida de restauracion:
  rechazar por su commit y no esconderla tras el snapshot final.

## Do / Don't
- DO verificar relaciones de ancestro con Git y probar la CLI real.
- DON'T convertir un ancestro ordinario en autorizacion de base externa.

## Tests
`tests/test_task_import_ancestry.py` crea repositorios y DAG reales con commits,
merges anidados, mutaciones restauradas, un clon superficial real y controles
de base externa.

## Constraints
PARAR y reportar si requiere cambiar oraculos anteriores, runtime o protecciones.
