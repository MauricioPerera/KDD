---
type: 'Task Contract'
title: 'Creacion directa de procesos en el Job Object'
description: 'Eliminar el interprete intermedio en Windows compatible conservando la contencion.'
tags: ['ci', 'windows', 'processes', 'performance']
task: process-job-at-creation
intent: 'Reducir arranques del controlador de procesos de Windows.'
target: scripts/process_tree.py
language: python
signature: 'def run(argv, *, cwd, timeout, **kwargs):'
test_command: 'python -m unittest tests.test_process_job_at_creation'
test_runner: python-unittest
test_scope: infrastructure
budget:
  cyclomatic_max: 18
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_process_job_at_creation.py
tests_sha256: '74190e30b2eb16c75c9392c9122a83f8ca890e8dc13c8be3414eca754a1bf845'
oracle_files: ['tests/test_process_job_at_creation.py', 'tests/__init__.py']
touch_only: ['scripts/process_tree.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

Reducir la preparacion repetida del
[ejecutor de CI](ci-trusted-execution.md). La asignacion en la creacion
preserva la [contencion](process-tree-timeout.md) y la
[barrera de terminacion](process-exit-barrier.md).

## Interface

Conservar la API de run y su CompletedProcess. En el perfil Windows
compatible, crear el objetivo en su Job con un solo lanzamiento del
objetivo. Su padre directo debe ser quien llama a run, incluso bajo un
Job exterior. El perfil POSIX conserva su grupo y su ruta directa.

## Invariants

- La asignacion al Job propio ocurre en la creacion, antes de ejecutar
  codigo del comando. Conservar propiedades de la barrera, los plazos y
  el aislamiento de invocaciones concurrentes.
- Conservar argv sin shell, Unicode, cwd, entorno, stdin, stdout y
  stderr, tanto separados como redirigidos. Preservar exit codes y los
  errores de ejecutable ausente, timeout, contencion y limpieza.
- Si el sistema carece del atributo de creacion, conservar la barrera
  anterior solo tras comprobar que no se inicio el objetivo. Un fallo
  de permisos o contencion sigue siendo error. No repetir un objetivo
  que pudo iniciar ni ejecutar una variante sin contencion.
- Conservar todos los IDs, dos suites independientes, Ubuntu y
  Windows, cobertura en la primera y el
  [plazo comun de post-init](postinit-windows-common-deadline.md).

## Examples

- Un comando con stdin y salidas separadas conserva sus datos y salida
  43, tambien bajo un Job exterior.
- Un proceso vivo pertenece al Job exacto de su invocacion.
- Una llamada vecina conserva sus resultados durante la cancelacion.

## Do / Don't

Usar procesos reales y comprobar handles del Job propio. Conservar las
pruebas existentes de arbol, pipes, plazos y limpieza.

## Tests

El oraculo prueba E/S real y la relacion de padre desde un llamador
normal y otro contenido. Verifica ademas la pertenencia al Job de un
hijo vivo, o a su propio grupo POSIX. Windows 10 y posteriores
comprueban la relacion directa. No se omiten casos en Ubuntu.
La [barrera](process-exit-barrier.md) conserva sus controles reales.

## Constraints

PARAR y reportar si falta el baseline revisado o se necesita otra
ruta protegida. Aprobar el runtime final por separado. Mantener gates,
workflows y protecciones. Acreditar la reduccion con tres CI
comparables del mismo candidato, incluyendo la ruta critica completa
del check Windows. El microbenchmark local solo mide una fase.
