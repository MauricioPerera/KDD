---
type: 'Task Contract'
title: 'Perimetro Git completo en la aprobacion de calidad'
description: 'Detectar cambios fuera de la politica en HEAD, el indice y el directorio de trabajo aunque Git oculte su estado.'
tags: ['quality', 'git', 'integrity']
task: quality-approval-perimeter
intent: 'Rechazar cambios fuera del perimetro de calidad aprobado.'
target: scripts/verify_quality.py
signature: 'def changed_paths(root, commit):'
test_command: 'python -m unittest tests.test_quality_approval_perimeter'
test_runner: python-unittest
oracle_files: ['tests/test_quality_approval_perimeter.py', 'tests/test_verify_quality.py', 'tests/test_quality_required_oracle_evidence.py', 'tests/test_quality_oracle_reviews.py', 'tests/test_mutation_control_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: tests/test_quality_approval_perimeter.py
tests_sha256: '3c00a097af7653b5e0885fa8bc51496a328185e472bc4842c3e7b69ad23c3d7a'
touch_only: ['scripts/verify_quality.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

Hacer efectivo el [perimetro aprobado](verify-quality.md) en las dos
modalidades de la CLI, incluido el [modo estricto](quality-required-oracle-evidence.md).

## Interface

La comprobacion de integridad conserva los argumentos y el codigo de salida
de la CLI. Identifica la ruta en un rechazo de perimetro o de integridad.

## Invariants

- Comprobar el diff entre los arboles originales del commit aprobado y de
  `HEAD` de manera independiente del indice y del directorio de trabajo.
  Restaurar una ruta fuera de alcance solo en el indice y el disco no oculta
  el cambio confirmado. Un revert confirmado que restaura el arbol si vale.
- Mantener las comprobaciones de cambios staged, unstaged y sin seguimiento
  no ignorados. Verificar las entradas `assume-unchanged` y `skip-worktree`
  aunque el diff ordinario no las muestre. Aceptar una ruta marcada que
  conserva su estado y los cambios de rutas autorizadas por la politica.
  Respetar la conversion de texto de Git y `core.filemode` al distinguir
  cambios reales. Bloquear si una entrada necesaria no puede medirse con
  fiabilidad.
- Comprobar tambien los archivos protegidos en el arbol de `HEAD`. Conservar
  la semantica aprobada de igualdad de contenido. Un archivo protegido
  regular debe seguir siendo regular y conservar su modo Git aprobado.
  Conservar la evidencia canonica de tareas. Los controles se repiten en las
  fronteras de integridad existentes.
- La comprobacion no cambia HEAD, el indice, sus flags ni los archivos del
  proyecto. Un check que oculta un cambio ajeno debe provocar un rechazo
  antes de la aprobacion final. Un rechazo previo a ejecutar checks no deja
  recibos de oraculo ni ejecuta comandos de la politica.

## Examples

- Un cambio oculto con `git update-index --assume-unchanged` fuera del
  perimetro devuelve un rechazo con la ruta.
- Un archivo permitido y modificado con `skip-worktree` admite las dos pasadas.

## Do / Don't

- DO conservar la lectura de objetos Git originales y los controles existentes.
- DON'T limpiar los flags del indice del proyecto para obtener un diff.

## Tests

Ejecutar la CLI real en repositorios Git temporales y el cuerpo del paso
estricto con el ejecutor aprobado. Comprobar los dos flags, la ausencia de
una ruta marcada, el indice restaurado frente a HEAD, la mutacion durante un
check y los controles de compatibilidad.

## Constraints

Conservar Ubuntu, Windows y las dos pasadas de la suite. Mantener el alcance
en el perimetro del verificador de calidad. PARAR y reportar si se necesita
cambiar el runtime de CI, el workflow o las protecciones remotas.
