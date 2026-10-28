---
type: 'Task Contract'
title: 'Limpieza estricta de fixtures Git existentes'
description: 'Completar mantenimiento antes de limpiar las fixtures de tareas y auditoria que fallaron en Ubuntu.'
tags: ['ci', 'git', 'integration']
task: existing-git-fixture-lifecycle
intent: 'Evitar mantenimiento desacoplado en las dos fixtures existentes sin debilitar pruebas ni alterar el entorno global.'
target: tests/test_task_git.py
language: python
signature: 'def __init__(self, oracle=None, *, automatic_maintenance=False):'
test_command: 'python -m unittest tests/test_existing_git_fixture_lifecycle.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 450
  params_max: 6
tests: tests/test_existing_git_fixture_lifecycle.py
tests_sha256: 'f59da515eebe850af25050243f41915998f8617da7ec3e2520581d3d80f20a09'
touch_only: ['tests/test_task_git.py', 'tests/test_validate_change_contract.py']
deps_allowed: ['stdlib', 'git', 'task_git', 'task_model', 'validate_change_contract', 'change_contract_multilang']
forbids: ['network', 'llm']
---

## Intent
Extender el [ciclo de vida local](ci-git-fixture-lifecycle.md) a Repository y
ChangeContractTests tras dos fallos reales en el PR130 de
[sintaxis de workflows](../workflow-syntax-ci.md). La revision de estos helpers
de oraculos sigue el [protocolo de calidad](../quality-approval.md).

## Interface
Justo despues de git init y antes del primer commit, cada fixture configura
maintenance.autoDetach=false y gc.autoDetach=false en su propio .git/config.
Los argumentos anteriores y todos los metodos/aserciones se conservan.
La [extension de fixtures efimeros](../task-quality-fixture-remediation.md)
agrega el keyword a Repository; estos controles solicitan True al construirlo.
ChangeContractTests conserva su configuracion anterior. Ambos controles
siguen ejercitando mantenimiento real sin detach.

## Invariants
El mantenimiento sigue habilitado en estos controles dedicados. No modificar configuracion global/sistema,
variables de CI, workflows ni runtime para compensar la carrera. La limpieza
permanece estricta, sin sleeps, reintentos, ignore_errors ni excepciones tragadas.
Conservar los 1234 IDs previos y agregar seis integraciones reales sin SKIP.
Los tres contratos que sellan estos helpers solo cambian tests_sha256.

## Examples
- El commit inicial y uno posterior invocan housekeeping y esperan su salida.
- Git moderno usa --no-detach; Trace2 muestra al hijo terminado antes del padre.
- Dejar autoDetach por defecto o desactivar mantenimiento falla el oraculo.

## Do / Don't
- DO: comprobar origen local, Git real y orden Trace2 en Windows/Ubuntu.
- DON'T: contar reruns verdes como correccion ni ocultar los dos fallos remotos.

## Tests
tests/test_existing_git_fixture_lifecycle.py verifica para cada fixture origen
local, mantenimiento habilitado y ambos commits sincronicos. Los dos oraculos
previos conservan sus metodos de prueba, aserciones y limpieza exactos.

## Constraints
Los cuatro cambios de helper se presentan con hashes y diff para revisar el
baseline antes de registrarlo o publicar la actualizacion del PR.
PARAR y reportar si se necesita otro oraculo, runtime o proteccion remota.
La suite completa y CI del nuevo SHA se ejecutaran despues de esa aprobacion;
no se declara eliminada toda flakiness por pasar seis casos dirigidos.
