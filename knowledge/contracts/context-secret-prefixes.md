---
type: 'Task Contract'
title: 'Limites de prefijos de credenciales en contexto'
description: 'Evitar falsos positivos en nombres Task sin perder el aborto de prefijos de credenciales.'
tags: ['context', 'quality', 'security']
task: context-secret-prefixes
intent: 'Corregir el falso positivo del nombre del contrato de worktrees conservando las otras reglas.'
target: ccdd/context.json
language: json
signature: 'guardrails.regex_deny.patterns'
test_command: 'python -m unittest tests/test_context_secret_prefixes.py'
budget:
  cyclomatic_max: 1
  nesting_max: 1
  lines_max: 100
  params_max: 1
tests: tests/test_context_secret_prefixes.py
tests_sha256: 'bfd0d26a4314869d7603d315873c788d78f9c816537531bf81d8d9ce019cde90'
touch_only: ['ccdd/context.json']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Resolver la regresion del [cierre de pendientes](../pending-improvements.md)
conservando la semantica del [ensamblador](assemble-context.md).

## Interface
Modificar exclusivamente el patron de prefijo sk- en ccdd/context.json:
reconocerlo al comienzo o despues de un caracter no alfanumerico ASCII,
conservar el minimo de 20 caracteres y su alfabeto actual. No tratar la
terminacion de la palabra task como una credencial.

## Invariants
Conservar presupuestos, slots, orden y los otros diez patrones; regex_deny
sigue on_fail abort. Prefijos sinteticos clasico, proj y svcacct deben
abortar, incluso tras comillas, espacios, salto de linea, igual, barra o
guion bajo. El CLI real debe aceptar el indice y el contrato de worktrees.
No modificar el ensamblador, los oraculos anteriores ni sus sellos.

## Examples
- task-worktree-integration -> contexto permitido.
- prefijo sk- seguido de 32 letras sinteticas -> GuardrailAbort.

## Do / Don't
- DO preservar las restantes reglas y probar el contexto real.
- DON'T desactivar regex_deny, excluir nodos ni contar un error como deteccion.

## Tests
Cinco casos nuevos con prefijos sinteticos, delimitadores, contexto real y
control de integridad del resto de la configuracion. Mantener en verde el
oraculo anterior del ensamblador sin cambiarlo.

## Constraints
PARAR y reportar si la correccion exige eliminar otros patrones o cambiar oraculos previos.
El baseline necesita revision humana explicita antes de aplicar la configuracion.
Es deteccion determinista por prefijo; no garantiza ausencia universal de secretos.
