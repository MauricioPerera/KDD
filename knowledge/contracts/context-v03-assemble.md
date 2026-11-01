---
type: 'Task Contract'
title: 'Compatibilidad CCDD v0.3 de contexto y guardrails'
description: 'Lee YAML v0.3, valida integridad y ensambla entradas con JSON Schema sin ejecucion de proveedores.'
tags: ['context', 'ccdd', 'compatibility']
task: context-v03-assemble
intent: 'Ensamblar de forma verificable contratos v0.3 de contexto existentes.'
target: scripts/context_v03.py
signature: 'def main():'
test_command: 'python -m unittest tests.test_context_v03'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: 'tests/test_context_v03.py'
tests_sha256: 'e22f4dd536caf44d3ca8c95b70302fddfeddbb3c86c103c3d0a6361881684ed7'
touch_only: ['scripts/context_v03.py']
deps_allowed: ['stdlib', 'PyYAML', 'jsonschema']
forbids: ['network', 'llm', 'subprocess']
---

## Intent
Aplicar lint y assemble del [perfil v0.3](../context-v03-compat.md).

## Interface
CLI `lint` y `assemble`, JSON y codigos definidos en el perfil enlazado.

## Invariants
- Validar esquema, entradas y hashes antes de entregar contexto.
- Fallar cerrado ante datos desconocidos, rutas inseguras o guardrails no soportados.
- No ejecutar proveedores ni imprimir valores sensibles en errores.
- Conservar presupuesto, orden, pisos y semantica de compactacion documentados.

## Examples
- Contrato v0.3, hashes e input valido -> payload y hash deterministas.
- JSON de slot contrario a su schema -> BLOCKED sin payload.

## Do / Don't
- DO: respetar el [ensamblador existente](assemble-context.md).
- DON'T: interpretar hashes como firmas de revisor ni usar red.

## Tests
Integraciones reales del CLI y sus archivos en `tests/test_context_v03.py`.

## Constraints
PARAR y reportar si la compatibilidad exige bajar guardrails o alterar oraculos anteriores.
