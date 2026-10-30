---
type: 'Task Contract'
title: 'Padres de commits leidos con la linea principal'
description: 'Auditar todos los commits e importaciones sin consultar los padres individualmente.'
tags: ['git', 'performance', 'integration']
task: task-history-parent-batch
intent: 'Leer padres por lote preservando el recorrido completo y el rechazo de estados intermedios invalidos.'
target: scripts/validate_tasks.py
language: python
signature: 'def validate_range(repo_root, base_ref, head_ref):'
test_command: 'python -m unittest tests/test_task_history_read_cost.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_task_history_read_cost.py
tests_sha256: 'ebffa345f9c0fe9fb1db9bcbcb17015f995fdffc764ec1348dfa22dbc511f000'
touch_only: ['scripts/validate_tasks.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [politica de historia y medicion](../task-history-read-cost.md)
conservando el [validador original](task-validation.md) y la
[publicacion por merge](task-publication.md).

## Interface
Conservar validate_range(repo_root, base_ref, head_ref) -> list y su CLI.
El formato y los errores publicos conservan el SHA del commit infractor.

## Invariants
Reutilizar las filas de padres del listado de primera linea sin omitir
ningun commit. Mantener snapshots, transiciones, scope, pruebas de cierre,
base en primera linea e importaciones recursivas con todos sus padres.

## Examples
- Publicar un diario completo conserva los commits y evidencia originales.
- Borrar una tarea y restaurarla despues sigue fallando en el commit intermedio.

## Do / Don't
- DO: contar invocaciones Git y comprobar el diario real completo.
- DON'T: validar solo el tip, inferir un unico padre para los merges o ejecutar candidatos.

## Tests
Oraculo compartido con task-ancestry-cache. Comprueba el recorrido real,
la ausencia de consultas individuales, importaciones, borrados y scope
intermedios, evidencia alterada, refs moviles y ausencia de efectos.

## Constraints
PARAR y reportar si cumplir exige cambiar los oraculos previos, el runtime,
los workflows, los limites o una proteccion. Implementar solo despues de
la revision humana del baseline de estos contratos y pruebas.
