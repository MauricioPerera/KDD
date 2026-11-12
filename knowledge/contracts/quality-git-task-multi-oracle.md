---
type: 'Task Contract'
title: 'Calidad con evidencia de tareas multiarchivo'
description: 'Auditar cierres Git multiarchivo con los oraculos y el helper de inventario congelados.'
tags: ['quality', 'tasks', 'git', 'integration']
task: quality-git-task-multi-oracle
intent: 'Aceptar evidencia multiarchivo con politica y auditor aprobados.'
target: scripts/verify_quality.py
signature: 'def approve(root, policy_path, reference):'
test_command: 'python -m unittest tests.test_git_task_multi_oracle'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  params_max: 5
tests: tests/test_git_task_multi_oracle.py
tests_sha256: '0bd2e672316a65247887e086c75b554973f2084f7f966ae1a562b9f06122803d'
oracle_files: ['tests/test_git_task_multi_oracle.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py']
touch_only: ['scripts/verify_quality.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

Extender la [evidencia de tareas seleccionadas](quality-task-evidence.md)
al [cierre multiarchivo](git-task-multi-oracle.md).

## Interface

La politica conserva `generated_task_evidence` y `protected`. Una tarea
declarada con inventario explicito requiere que la politica aprobada proteja
todos sus archivos de inventario y `scripts/oracle_inventory.py`, ademas
de los validadores canonicos del diario.

## Invariants

- Leer contrato, politica y helper desde la referencia revisada. Extraer
  el helper protegido al bundle aislado del auditor cuando se declara en
  la politica. Los proyectos de un archivo sin inventario conservan el
  bundle historico de cinco modulos.
- Rechazar un auxiliar de inventario o helper del auditor sin proteccion
  antes de ejecutar los checks. Un archivo no protegido del checkout
  no puede completar el bundle ni alterar la auditoria.
- Cuando el contrato de la politica o de la tarea declara inventario,
  vincular el contrato y cada auxiliar aprobado para el cierre a los
  bytes de la aprobacion de calidad. Las referencias pueden diferir
  si esos artefactos coinciden. El commit probado tambien debe respetar
  las declaraciones binarias de calidad. Restaurar un auxiliar al final no
  acredita el cierre que utilizo otros bytes.
- Verificar la integridad de los binarios inventariados con las
  declaraciones del commit aprobado, antes y despues de los checks.
- Verificar historial, recibos y perimetro con el auditor congelado y
  ejecutar dos veces cada check aprobado. Mantener los tests y checks de
  la politica previa y la matriz Ubuntu y Windows.

## Examples

- Dos modulos aprobados y dos filas canonicas pasan calidad tras el cierre.
- La politica omite un archivo auxiliar o el helper del inventario. El
  verificador rechaza la aprobacion antes del primer check.
- Un cierre con un auxiliar distinto, seguido de su restauracion, se
  rechaza aunque la copia final coincida con el commit de calidad.

## Do / Don't

- DO comprobar las politicas con el runner extraido de Git.
- DON'T importar un helper del checkout al validar evidencia congelada.

## Tests

El oraculo usa proyectos temporales con un baseline sintetico, cierres Git
reales y un runner de calidad extraido del commit aprobado. Comprueba los
dos resultados de cada check y el rechazo previo a la ejecucion.

## Constraints

PARAR y reportar si el cambio requiere actualizar una politica aprobada
real o cambiar controles remotos.
