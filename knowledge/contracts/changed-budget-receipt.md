---
type: 'Task Contract'
title: 'Recibo del alcance de presupuestos del cambio'
description: 'Registrar el alcance y la medicion efectiva de los presupuestos Python del diff.'
tags: ['quality', 'budget', 'ci']
task: changed-budget-receipt
intent: 'Distinguir un cambio medido de un cambio fuera del alcance del auditor.'
target: scripts/validate_changed_budgets.py
language: python
signature: 'def main():'
test_command: 'python -m unittest tests.test_changed_budget_receipt'
test_runner: python-unittest
oracle_files: ['tests/test_changed_budget_receipt.py', 'tests/quality_review_fixture.py', 'tests/test_fixture_preparation.py']
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_changed_budget_receipt.py
tests_sha256: '0fa45479c19f06a49ab612930941c2bf0baf2b9ba839bc37ff960401a73b6177'
touch_only: ['scripts/validate_changed_budgets.py', 'knowledge/validacion.md']
deps_allowed: ['stdlib', 'validate_budgets', 'validate_contracts']
forbids: ['llm', 'network']
---

## Intent

Hacer observable el alcance del [auditor Python](changed-python-budgets.md) en
cada comparacion, incluso cuando el diff no activa ninguna medicion.

## Interface

La interfaz existente conserva salida y codigos. La opcion `--json` emite
un objeto UTF-8 con `schema_version: 1`, `base_ref`, `head_ref`, `regression_status`,
`files` y `findings`. En un diff valido cada ruta del recibo usa
`path`, `status`, `contracts` y `measurements`. Una medida identifica
`contract`, `function` calificada, `metrics` con los cuatro valores AST, `limits` con los topes aplicados y el booleano `within_budget` calculado comparando cada metrica declarada con su tope aprobado.
Repetir el mismo rango y politica produce el mismo recibo aunque haya
ediciones locales o archivos sin seguimiento.
`findings` conserva los diagnosticos del auditor. `regression_status` es `PASS`
o `FAIL`. Los errores de lectura, seleccion, rango o analisis devuelven
distinto de cero y un diagnostico; solo un diff completo produce un recibo.

## Invariants

- Incluir cada ruta diferente entre los dos arboles exactamente una vez.
  Ordenar por ruta y ordenar los contratos y medidas por contrato y funcion.
  Leer objetos Git originales del rango validado. Un renombre se refleja como
  eliminacion y alta cuando Git expone ambas rutas.
- `measured` exige al menos una medida efectiva. Si hay politicas aplicables
  y el blob se proceso sin funciones candidatas nuevas o modificadas, el
  estado es `no_changed_functions`. Los estados de exclusion son
  `deleted`, `not_python` y `no_python_contract`, en ese orden de
  precedencia. Una exclusion lleva contratos y medidas vacios.
- Emitir el recibo tanto para cambios validos dentro del tope como para
  excesos. El exit code y el veredicto concuerdan. Los errores de cobertura
  requerida del [control de producto](quality-required-controls.md) conservan
  su politica y recibo propios.
  Una deuda tolerada por el gate diferencial conserva within_budget=false.
  Solo una medida efectiva puede demostrar cumplimiento. Ausencia de medida
  o veredicto diferencial favorable no acreditan cumplimiento absoluto.
- Conservar las reglas diferenciales, la politica del commit base cuando
  corresponda, los sellos, las cuatro metricas y el contrato previo. Una
  ruta secundaria en touch_only queda visible con su motivo de exclusion.
  Conservar Ubuntu y Windows, las dos pasadas, cobertura en la primera y
  ventana de post-init de Windows inferior a 600 s.

## Tests

CLI Python y repositorios Git reales. Se coteja el inventario exacto de rutas
del diff y el veredicto, incluyendo un cambio equivalente al del relevo Board,
comentarios, medidas, excesos, eliminaciones, multiples politicas y rango invalido.

## Examples

- Un diff cambia un objetivo TS y un auxiliar Python sin contrato. El recibo
  contiene las dos rutas, con `not_python` y `no_python_contract`.
- Una funcion nueva supera la ciclomática permitida. Su ruta es `measured`,
  se conserva `BUDGET_CYCLOMATIC` y la salida es 1.

## Do / Don't

- DO contrastar cada medida con sus limites efectivos mediante el analizador.
- DON'T usar una etiqueta de agente, un exit 0 o una exclusion como medida.

## Constraints

La evidencia es reproducible sin modelos ni red. Cambiar las reglas de conteo
o el significado de los presupuestos requiere un contrato independiente.
PARAR y reportar si hace falta cambiar las metricas o los presupuestos previos.
