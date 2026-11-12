---
type: 'Task Contract'
title: 'Oraculos multiarchivo en tareas Git'
description: 'Proteger el inventario aprobado y acreditar cada archivo seleccionado al cerrar una tarea Git.'
tags: ['tasks', 'git', 'quality', 'integration']
task: git-task-multi-oracle
intent: 'Cerrar y auditar tareas Git con varios archivos de prueba aprobados.'
target: scripts/task_git.py
signature: 'def contract_metadata(root, data, revision, *, committed_only=False):'
test_command: 'python -m unittest tests.test_git_task_multi_oracle'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 5
tests: tests/test_git_task_multi_oracle.py
tests_sha256: '0bd2e672316a65247887e086c75b554973f2084f7f966ae1a562b9f06122803d'
oracle_files: ['tests/test_git_task_multi_oracle.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py']
touch_only: ['scripts/task_git.py', 'scripts/task_evidence.py', 'scripts/oracle_execution.py', 'scripts/validate_tasks.py', 'knowledge/git-tasks.md', 'knowledge/data_models/git-task.md']
deps_allowed: ['stdlib', 'oracle_execution', 'oracle_inventory']
forbids: ['network', 'llm']
---

## Intent

Extender el [cierre instrumentado de un archivo](task-oracle-execution-proof.md)
a la seleccion explicita que admite el [inventario](oracle-inventory.md).

## Interface

`tasks.py ready`, `start`, `finish` y `validate_tasks.py` conservan su
interfaz. Para varios archivos, el contrato aprobado declara `test_runner`
y `oracle_files`. El comando elige archivos o modulos unittest explicitos
con un solo interprete Python, o archivos explicitos de `node --test`.
La opcion TAP historica conserva su sintaxis. El recibo v2 usa
`oracle_results` con una fila por archivo de pruebas seleccionado.

## Invariants

- Incluir `tests` exactamente una vez. Las rutas canonicas seleccionadas son
  distintas y forman un subconjunto del inventario aprobado. Un auxiliar
  inventariado puede participar sin producir casos propios. En la seleccion
  de un solo archivo se conserva la inferencia historica de runner.
- Rechazar seleccion sin inventario, runner ausente o incompatible para
  varios archivos, alias duplicados, rutas ambiguas o que escapan, opciones
  adicionales y nombres no inventariados antes de ejecutar. Los rechazos de
  seleccion usan el diagnostico TASK_RUNNER.
- Desde `ready` hasta el cierre, comprobar el contrato y todo su inventario
  contra el commit aprobado en Git y en el checkout cuando corresponda.
  Cada ruta es regular en los commits y cumple los controles locales
  de enlaces de tareas Git. Comparar texto con la normalizacion canonica y
  binarios con las reglas del inventario aprobado, incluida la declaracion
  `-text` en el commit aprobado. El sello primario sigue siendo obligatorio.
  Revalidar el inventario y los artefactos tras ejecutar y antes de publicar,
  incluso si Git oculta un cambio del checkout con assume-unchanged.
- Cada archivo seleccionado aporta casos reales, positivos y sin omisiones.
  Si uno falla, queda vacio o se omite, conservar estado, referencias y
  evidencia previa. El timeout cubre la invocacion completa y el runner
  conserva el interprete declarado, el aislamiento y UTF-8.
- El auditor usa el contrato aprobado y los objetos Git, sin ejecutar las
  pruebas ni leer sus bytes desde el checkout. El recibo v2 exige las rutas
  exactas seleccionadas, conteos positivos, suma coherente y claves JSON
  unicas. Un recibo v1 solo acredita la seleccion historica de un archivo.
  Los recibos v1 y v2 validos de un archivo se siguen leyendo.
- Conservar el perimetro, la ascendencia, la contencion y la contabilidad
  previa. Mantener las dos pasadas en Ubuntu y Windows.

## Examples

- `python -m unittest tests/test_price.py tests.test_rounding` con ambos
  archivos y sus auxiliares aprobados produce dos filas en `oracle_results`.
- Un segundo archivo sin casos o un auxiliar modificado bloquea el cierre.
- Un recibo con una fila adicional, ausente o repetida se rechaza aunque se
  haya recalculado su sello externo.

## Do / Don't

- DO reutilizar el runner instrumentado y el inventario exacto.
- DON'T convertir opciones libres, glob o salida impresa en evidencia.

## Tests

Integraciones con repositorios Git temporales, comandos reales Python y
Node, cierres y mutaciones de evidencia. Incluyen proteccion de auxiliares
no seleccionados, bytes binarios, rechazo de drift y lectura historica.

## Constraints

PARAR y reportar si se requiere cambiar una proteccion remota, un runtime
fijado o un oraculo fuera del alcance aprobado.
