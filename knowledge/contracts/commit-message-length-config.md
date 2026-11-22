---
type: 'Task Contract'
title: 'Validar el largo configurado del mensaje de commit'
description: 'Rechazar un largo de cabecera invalido con CONFIG_INVALID y exit 1.'
tags: ['ccdd', 'git', 'gate']
task: commit-message-length-config
intent: 'Validar el valor max_subject_length del JSON al entrar por el CLI.'
target: scripts/validate_commit_message.py
signature: 'def main(argv):'
test_command: 'python -m unittest tests/test_commit_message_length_config.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_commit_message_length_config.py
tests_sha256: '9caf4abad2bfdd4eb659dae417c30450146e73648808919e044515d723cb2183'
touch_only: ['scripts/validate_commit_message.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Aplicar la interfaz de [commit-message-gate](commit-message-gate.md) cuando
el JSON se puede leer pero contiene un largo sin sentido.

## Interface

En `main(argv)`, exigir que `max_subject_length` sea un entero no negativo.
Un valor invalido produce `ERROR [CONFIG_INVALID]`, menciona la clave y
devuelve 1 antes de validar el mensaje. Conservar las claves obligatorias y
la interfaz de `check_commit_message`.

## Invariants

Los booleanos, flotantes, cadenas, null, listas, objetos y numeros negativos
son invalidos. El valor cero conserva la advertencia de largo sin bloquear.

## Examples

- `null` produce un error de configuracion.
- `0` produce una advertencia para una cabecera valida.
- `72` admite una cabecera de menos de 72 caracteres.

## Do / Don't

- DO: usar la convencion de diagnosticos del CLI existente.
- DON'T: editar el oraculo historico ni ampliar el cambio a otras claves.

## Tests

Ejecutar el [oraculo sellado](../../tests/test_commit_message_length_config.py)
y el comando del [contrato anterior](commit-message-gate.md).

## Constraints

Limitar la implementacion a `scripts/validate_commit_message.py`.
PARAR y reportar si se requiere cambiar el oraculo o la interfaz existente.
