---
type: 'Task Contract'
title: 'Motor de reglas declarativo (rule contract)'
description: 'Checker determinista que evalua un record contra un rule-set declarativo (required/type/enums/bounds/refs/keyed) y devuelve las violaciones, sin LLM.'
tags: ['ccdd', 'rule-contract', 'reglas', 'declarativo']

task: validate-rules
intent: "Evaluar un record contra un rule-set declarativo y devolver las violaciones de forma determinista."
target: scripts/rule_engine.py
signature: "def evaluate(ruleset: dict, record: dict, refs: dict) -> list:"
test_command: "python -m unittest tests/test_rule_engine.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_rule_engine.py"
tests_sha256: "154fb9f6e2645161930fb03728dedc5dde422d6aa3e55ac7a39a889cccc1c319"
touch_only: ['scripts/rule_engine.py', 'scripts/validate_rules.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: validate-rules

## Intent
Motor de la vertiente rule contract: convierte las familias declarativas de
[rule-contract-spec](../rule-contract-spec.md) en un veredicto determinista sobre un
record, sin LLM ni red. Es el que hace posible verificar reglas de negocio como DATOS.

## Interface
```python
def evaluate(ruleset: dict, record: dict, refs: dict) -> list:
    """Evalua `record` contra `ruleset` (familias declarativas), resolviendo las
    familias keyed contra `refs`. Devuelve una lista de violaciones legibles (vacia =
    valido), ordenada deterministamente; cada violacion empieza con '<field>: ...'
    (field puede ser punteado/anidado). Funcion pura: sin IO, sin red, determinista."""
```

## Invariants
- Familias soportadas: `required` (ausente/None/"" -> violacion), `type`
  (number|string|dict; number excluye bool; solo si el valor esta presente), `bounds`
  (gt/min/max/integer; solo sobre numbers), `enums` (igualdad de valor, `in`), `refs`
  (el valor debe ser clave en `refs[collection]`), `keyed_bounds` y `keyed_enums` (el
  tope/conjunto se busca en `refs[table][record[key]]`; se saltan si la clave no resuelve).
- `each` ({collection, where?, rules}): cuantificacion sobre colecciones — el subset
  interno v1 (required/type/enums/bounds, misma semantica) se evalua sobre cada elemento
  dict de la lista `record[collection]`, filtrado por `where` {field, equals}; toda
  violacion lleva el prefijo del nombre de la coleccion (el campo top-level ES la
  coleccion); coleccion ausente o no-lista se salta; elemento no-dict = violacion de la
  coleccion nombrando el indice.
- Campos punteados (`beneficiary.account`) navegan dicts anidados; un intermedio no-dict se
  trata como ausente.
- Orden estable de violaciones (por campo); nunca lanza ante record/ruleset con tipos
  arbitrarios; una violacion por campo-familia como maximo.
- El motor NO conoce el dominio de pagos: solo interpreta el rule-set. La clave `code_only`
  del rule-set no la evalua el motor (es documentacion de la frontera).
- Determinista, pura, stdlib; sin red; sin subprocess; mensajes ASCII.

## Examples
- `evaluate({"required":[{"field":"a"}]}, {}, {})` -> 1 violacion que nombra `a`.
- `evaluate({"type":[{"field":"n","kind":"number"}]}, {"n": True}, {})` -> viola `n`
  (bool no es number).
- `keyed_bounds` de `amount` con `country="AR"` y monto sobre `limits.AR.max_amount` ->
  viola `amount`; con `country` fuera de `limits` -> no dispara (lo cubre `refs`).

## Do / Don't
- DO: navegacion de campos punteada; orden determinista; mensajes que nombren el campo.
- DO: saltar keyed cuando la clave no resuelve (evita falsos positivos y crashes).
- DON'T: red, subprocess, IO, dependencias fuera de stdlib; ejecutar `code_only`; importar
  el validador de codigo de pagos (el motor es agnostico al dominio).
- DON'T: tocar el oraculo, el rule-set de pagos, el golden ni el test de equivalencia.

## Tests
(Los tests estan en `tests/test_rule_engine.py`, autorados por el orquestador y congelados
por `tests_sha256`: el implementador no los escribe ni los modifica. Prueban cada familia
por separado + determinismo + robustez, con rulesets sinteticos, sin el dominio de pagos.)

## Constraints
- PARAR y reportar si... una familia del oraculo exigiera red/subprocess o algo imposible
  con stdlib puro, o si el oraculo congelado fuera internamente contradictorio.
