---
type: 'Task Contract'
title: 'Ciclo de vida sincronico de los repositorios Git de prueba'
description: 'Evitar que mantenimiento Git desacoplado compita con la limpieza estricta de un fixture temporal.'
tags: ['ci', 'git', 'verification']
task: ci-git-fixture-lifecycle
intent: 'Completar mantenimiento antes de devolver cada comando del fixture sin debilitar sus oraculos.'
target: tests/test_generated_task_evidence.py
language: python
signature: 'def __init__(self, root, count=1, initialize=True, *, automatic_maintenance=False):'
test_command: 'python -m unittest tests/test_ci_git_fixture_lifecycle.py'
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 100
  params_max: 4
tests: tests/test_ci_git_fixture_lifecycle.py
tests_sha256: '5fa07ff258cbd7e5fb294e3a907f9f6452024b477b667360d4f29aeb9aa386f5'
touch_only: ['tests/test_generated_task_evidence.py']
deps_allowed: ['stdlib', 'git']
forbids: ['network', 'llm']
---

## Intent
Completar el [protocolo de tiempo total](../ci-runtime.md) y conservar la
[evidencia generada](quality-task-evidence.md) tras el fallo real de limpieza
detectado por la segunda pasada Ubuntu del PR123.

## Interface
TaskProject conserva argumentos anteriores y agrega el keyword descrito en
el [modo efimero](../task-quality-fixture-remediation.md). Los dos controles
dedicados solicitan automatic_maintenance=True antes del primer commit.
Ese modo configura, en el repositorio temporal recien
inicializado y antes del primer commit, maintenance.autoDetach=false y
gc.autoDetach=false. El mantenimiento sigue habilitado: solo se ejecuta
sin desacoplarse. La configuracion no sale del .git/config de ese fixture.

## Invariants
Conservar todos los metodos, aserciones, umbrales de procesos, datos de producto,
timeouts y el modo dedicado del helper. Solo se adaptan las dos llamadas
de preparacion para solicitar ese modo; no cambiar isolated_env ni configuracion
del usuario, sistema, workflow o verificador para compensar el fallo.
TemporaryDirectory.cleanup sigue siendo estricto: no usar ignore_errors,
ignore_cleanup_errors, reintentos, sleeps ni excepciones tragadas.
Las cinco pruebas de git-read-batching conservan bytes y sello anteriores;
su proteccion del objeto ausente sigue siendo un rechazo real del producto.

## Examples
- Git moderno invoca mantenimiento con --no-detach y termina antes del commit.
- mantenimiento aun habilitado, limpieza normal sin procesos escribiendo tarde.
- Desactivar mantenimiento en el control dedicado o ignorar Directory not empty no satisface el contrato.

## Do / Don't
- DO: usar Git real y Trace2; verificar orden de terminacion y origen local.
- DON'T: contar un reintento verde como correccion del fallo ni ocultar el intento rojo.

## Tests
tests/test_ci_git_fixture_lifecycle.py comprueba configuracion local y
mantenimiento real completado antes del retorno del commit. Versiones de
Git anteriores a autoDetach conservan comprobacion de finalizacion, sin SKIP.
Las pruebas anteriores siguen ejecutandose; el cambio de helper y su sello
requiere baseline humano revisado antes de registrarlo o publicarlo.

## Constraints
PARAR y reportar si se necesita reducir cobertura, ignorar errores de limpieza
o modificar configuracion fuera del fixture temporal. Solo stdlib y Git.
No se declara eliminada toda flakiness; dos runs completos verdes de la misma
revision siguen siendo necesarios para cerrar la medicion.
