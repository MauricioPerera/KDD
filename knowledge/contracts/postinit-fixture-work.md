---
type: 'Task Contract'
title: 'Reducir la preparacion repetida de fixtures Git del post-init'
description: 'Preparar una base Git por clase y copiar solo las dependencias del fixture de tareas.'
tags: ['git', 'performance', 'bootstrap', 'integration']
task: postinit-fixture-work
intent: 'Reducir arranques Git y escrituras conservando ejecuciones reales y aislamiento por caso.'
target: tests/test_generated_task_evidence.py
signature: 'def __init__(self, root, count=1, initialize=True, *, automatic_maintenance=False):'
test_command: 'python -m unittest tests.test_postinit_fixture_work'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tests/test_postinit_fixture_work.py
tests_sha256: '1d4e27505718cd0d9f884c795cb7ab870821055014f924784fb7b3975de39749'
oracle_files: ['tests/test_postinit_fixture_work.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['tests/test_generated_task_evidence.py', 'tests/test_group_contracts.py', 'tests/test_ci_trusted_execution.py', 'tools/ci/postinit-module-order.json']
deps_allowed: ['stdlib', 'tests']
forbids: ['network', 'llm']
---

## Intent

Reducir el trabajo de preparacion observado en el
[post-init Windows](postinit-command-timing.md), usando el aislamiento
de [fixtures de perimetro](postinit-perimeter-setup.md).

## Interface

Conservar TaskProject y los fixtures de grupo y de runtime confiable.
Un proyecto sintetico nuevo copia los cinco modulos de auditoria aprobada,
los dos puntos de entrada de tareas y calidad, la contencion y el lector de
inventario. Los nueve archivos deben corresponder byte a byte al checkout.
La inicializacion no elimina archivos que ya trae un proyecto consumidor.

Los oraculos de grupo y runtime crean un commit base real por clase y
proceso. Cada caso recibe un clon Git local con archivos, indice, refs y
objetos independientes. Los clones se configuran antes del checkout
para conservar los bytes incluso con una conversion de finales de linea heredada.
Las llamadas directas a setUp sin preparacion de clase conservan una
preparacion Git independiente. Limpiar una clase retira su base.

## Invariants

- Conservar los casos, aserciones, plazos y flujos publicos existentes.
  La base es solo preparacion. Cada caso ejecuta sus comandos y produce
  sus propias salidas y evidencias; no comparte resultados ni marcadores.
- El primer cambio en un clon no altera la base ni otro caso. No usar
  hardlinks entre worktrees ni compartir la base de objetos. Conservar
  los ajustes locales de identidad y mantenimiento y la limpieza.
- Mantener Ubuntu y Windows, los 2.230 IDs previos, las dos pasadas
  generales y el post-init nativo. Mantener diez procesos en Windows,
  cuatro en Ubuntu y los deadlines. El perfil de orden puede incorporar
  mediciones reales conforme a [su contrato](postinit-module-order.md).
- Aceptar rendimiento solo tras tres ejecuciones consecutivas completas
  del mismo SHA en main, todas con Windows post-init inferior a 480 s.

## Examples

- Dos casos que comparten base ejecutan el mismo grupo sobre clones
  distintos y cada uno genera sus propios eventos.
- Cambiar un objeto o el indice de un clon no alcanza al otro ni a la base.
- Un TaskProject con archivos adicionales del consumidor los conserva.

## Do / Don't

- DO contar git init y git clone con Trace2 y verificar bytes del commit.
- DON'T copiar scripts ajenos a un proyecto nuevo ni convertir falta
  de infraestructura en una omision del oraculo.

## Tests

Git y Python reales comprueban el presupuesto de preparacion, aislamiento
y ejecucion por clon. El ciclo completo de una tarea prueba que el conjunto
reducido sirve para crear, aprobar, cerrar y verificar evidencia real.
Los oraculos historicos conservan sus casos y aserciones.

## Constraints

PARAR y reportar si falta el baseline humano o se requiere cambiar
runtime, workflow, proteccion o un oraculo fuera de este perimetro.
