---
type: 'Task Contract'
title: 'Vincular el guard confiable al evento del PR'
description: 'Comprobar el merge real contra ambos padres exactos antes de seleccionar su aprobacion.'
tags: ['ci', 'security', 'git']
task: trusted-pr-event-binding
intent: 'Vincular el candidato del guard con la base y el head del evento del PR.'
target: scripts/guard_pr_baseline.py
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests.test_trusted_pr_event_binding'
test_runner: python-unittest
budget:
  cyclomatic_max: 20
  nesting_max: 4
  params_max: 6
tests: tests/test_trusted_pr_event_binding.py
tests_sha256: 'b976663415fbeaf8b30ff24de265bdd0f8067ae1ad00572d0840aa56c3775b6f'
oracle_files: ['tests/test_trusted_pr_event_binding.py', 'tests/test_approval_registry.py', 'tests/__init__.py']
touch_only: ['scripts/guard_pr_baseline.py', '.github/workflows/trusted-pr-gate.yml']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent

Mantener la frontera del [guard confiable](trusted-pr-gate.md) cuando
`refs/pull/N/merge` cambia despues de emitirse el evento.

## Interface

El CLI del guard requiere `--base-ref` y `--head-ref` con los OID completos
de commits del formato nativo. El workflow toma ambos del mismo payload y
obtiene su codigo confiable de la base exacta. La API `check` conserva su
contrato de comparacion de objetos y revision externa.

## Invariants

- Leer los padres originales del objeto de merge obtenido de `origin`, sin
  sustituciones ni inferencias de ascendencia. Debe tener exactamente dos
  padres ordenados `[base, head]`. La discrepancia devuelve `PR_EVENT_MISMATCH`. Un commit simple, un merge con mas padres,
  un head distinto o una base distinta devuelve error antes de consultar el
  registro, la revision de cambios protegidos o la aprobacion explicita.
- Referencias simbolicas, abreviadas, no canonicas, o un OID que no identifica
  al commit nativo requerido se rechazan. El candidato validado se identifica
  por el OID resuelto, incluso si el ref remoto cambia despues de la lectura.
- Los cambios protegidos de un merge correcto conservan su veredicto previo.
  Se conserva la validacion por arbol del registro externo y la revision
  exacta de cambios protegidos. Ningun codigo del candidato se ejecuta.
- El workflow conserva `pull_request_target` y permisos de lectura.

## Examples

- Merge del evento A sobre la base B, en orden B y A, continua al guard.
- Si el ref cambia a un merge de C, el resultado es error aun con su arbol
  aprobado. Lo mismo ocurre si el head sigue en A y la base avanza.

## Do / Don't

- DO conservar el arbol real de la propuesta para la comparacion.
- DON'T inferir identidad por el numero del PR, el nombre de una rama o
  coincidencia del arbol.

## Tests

El oraculo usa remotos bare y merges Git reales. Comprueba coincidencia,
desfase de head y base, commit no merge, orden y referencias incompletas.
Los fixtures de routing y revision externa suministran ambos SHA y conservan
las aserciones sobre aprobaciones y cambios protegidos.

## Constraints

El contrato cubre la atribucion de la ejecucion del guard. La proteccion de
rama y la configuracion externa de GitHub quedan bajo su control actual.

PARAR y reportar si validar la identidad requiere cambiar permisos o protecciones remotas.
