---
type: 'Task Contract'
title: 'Presupuestos de complejidad de funciones modificadas'
description: 'Impedir excesos nuevos o agravados en objetivos Python contratados mediante un diff de commits.'
tags: ['quality', 'budget', 'ci']
task: changed-python-budgets
intent: 'Bloquear regresiones de complejidad en funciones Python contratadas.'
target: .github/workflows/validate.yml
language: yaml
signature: 'audit_changed_python_budgets(validate, base_ref, head_ref)'
test_command: 'python -m unittest tests.test_changed_python_budgets'
test_runner: python-unittest
oracle_files: ['tests/test_changed_python_budgets.py', 'tests/quality_review_fixture.py', 'tests/test_fixture_preparation.py']
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_changed_python_budgets.py
tests_sha256: '85ce3d59c29b6dfc1fd7395c954579a3d2d50c9a8dc1aa7ea15dae9143b7edd3'
touch_only: ['scripts/validate_changed_budgets.py', '.github/workflows/validate.yml', 'knowledge/validacion.md']
deps_allowed: ['stdlib', 'validate_budgets', 'validate_contracts']
forbids: ['llm', 'network']
---

## Intent

Aplicar los [presupuestos Python](../validacion.md) a la deuda nueva. El
diagnostico global y los presupuestos historicos siguen sirviendo para medir
deuda preexistente.

## Interface

python scripts/validate_changed_budgets.py knowledge/contracts --repo-root . --base-ref
BASE --head-ref CANDIDATO. Ambos OID nativos completos identifican commits y
BASE es ancestro de CANDIDATO. Salida 1 con excesos o datos invalidos. La salida
identifica contratos, objetivos, funciones y metricas examinados.

## Invariants

- Leer contratos, objetivos y diff de los commits originales sin reemplazos
  Git. Para contratos preexistentes aplicar limites y objetivo del commit base
  incluso si el candidato cambia o borra ese contrato. Para contratos nuevos
  usar sus topes del candidato con sello de oraculo valido y comparar con el
  objetivo de base, si existe.
- En funciones nuevas exigir el tope. En una funcion existente cambiada,
  rechazar cada metrica sobre el tope cuando aumenta frente a la base.
  La deuda igual o reducida puede pasar. Usar las metricas AST existentes.
- Una funcion sin cambios sigue su diagnostico historico, incluso si se agrega un contrato. Identificar funciones
  por ambito y nombre, sin confundir metodos homonimos de clases distintas.
  Una medicion requerida que no puede leer o analizar un blob Python bloquea.
- El alcance es objetivos .py con presupuesto en contratos existentes o nuevos.
  Eliminaciones de codigo no generan excesos. No atribuir la medicion a otros
  lenguajes ni a codigo sin contrato.
- CI nativo de KDD aplica el control al merge probado en PR y al intervalo
  del push de main. La ruta de CI reutilizable conserva su politica existente.
  No ejecutar la suite para obtener la medicion.

## Tests

Repositorios Git reales con deuda previa, regresiones de complejidad, mejoras
parciales, limites manipulados y metodos homonimos. CI comprueba que el
intervalo de comparacion existe y apunta al checkout probado.

## Examples
- Limite 8, base 11 y candidato 10 aprueba la mejora.
- Limite 8, base 11 y candidato 12 devuelve BUDGET_CYCLOMATIC.

## Do / Don't
- DO comprobar los objetos del checkout probado en CI.
- DON'T bloquear excesos historicos iguales ni aumentar un limite aprobado.

## Constraints
Conservar el medidor historico y los umbrales de todos los contratos previos.
PARAR y reportar si se necesita cambiar un presupuesto previo o medir otro lenguaje.
