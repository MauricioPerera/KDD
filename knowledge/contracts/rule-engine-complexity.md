---
type: 'Task Contract'
title: 'Reducir complejidad del motor de reglas'
description: 'Cumplir el presupuesto original del motor de reglas sin cambiar sus resultados.'
tags: ['quality', 'budget', 'rules', 'refactoring']
task: rule-engine-complexity
intent: 'Reducir los excesos del motor declarativo preservando comportamiento y oraculos.'
target: scripts/rule_engine.py
signature: 'def evaluate(ruleset: dict, record: dict, refs: dict) -> list:'
test_command: 'python -m unittest tests.test_rule_engine_complexity'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_rule_engine_complexity.py
tests_sha256: 'a287804056b4e4764c34240104c51f9f12dd75795abc8ab1c74547e61c1600b7'
touch_only: ['scripts/rule_engine.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess']
---

## Intent
Reducir la deuda medida en [validate-rules](validate-rules.md) sin modificar
el presupuesto ni sus pruebas congeladas. La linea base de main registra seis
excesos sobre tres funciones, de ciclomaticidad y anidamiento.

## Interface
Conservar la interfaz publica y mensajes de [validate-rules](validate-rules.md).

## Invariants
Cumplir los limites originales de ciclomaticidad 10 y anidamiento 4 para todas
las funciones del target, incluidos helpers nuevos. Conservar familias, orden
estable, validacion de valores no finitos, referencias, datos de entrada, goldens
y comportamiento de `each`. Mantener pureza y dependencias stdlib.
No alterar contratos o pruebas existentes, sus sellos ni los limites.

## Examples
- Una regla keyed con limite invalido sigue reportando el mismo mensaje.
- El validador real reproduce los rule sets y goldens del repositorio.

## Do / Don't
- DO comparar el diagnostico global con el mismo SHA y verificar ambas plataformas.
- DON'T presentar los duplicados de contratos con igual target como funciones distintas.

## Tests
El oraculo nuevo comprueba el presupuesto original, combinaciones de familias,
mensajes exactos, ausencia de mutacion y reproduccion real de goldens sellados.
La suite original del motor y del validador permanece intacta.

## Constraints
PARAR y reportar si preservar comportamiento exige cambiar un oraculo existente
o si el inventario global muestra hallazgos nuevos o agravados.
