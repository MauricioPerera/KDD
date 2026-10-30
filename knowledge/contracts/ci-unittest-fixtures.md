---
type: 'Task Contract'
title: 'Semantica unittest para fixtures y load_tests'
description: 'Representar omisiones reales y reconstruir suites de origen sin falsificar ejecucion.'
tags: ['ci', 'testing', 'integration']
task: ci-unittest-fixtures
intent: 'Corregir los falsos rechazos manteniendo inventario completo y fallos visibles.'
target: scripts/run_test_suite.py
language: python
signature: 'def validate_report(expected_ids, report) -> list:'
test_command: 'python -m unittest tests/test_ci_unittest_fixtures.py'
budget:
  cyclomatic_max: 18
  nesting_max: 4
tests: tests/test_ci_unittest_fixtures.py
tests_sha256: '63bd62e71c38da70692c0163e0663754a4b18a07d5bb2b7cb28651eca945f25b'
touch_only: ['scripts/run_test_suite.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Extender [suite por procesos](ci-suite-processes.md) con el
[modelo de inventario](../ci-audit-remediation.md), sin relajar sus rechazos.

## Interface
- Mantener CLI, API, version=1 y campos actuales para casos ordinarios.
- Agregar fixture_omitted_ids (ordenados/unicos) y fixture_outcomes: cada resultado
  lleva id de fixture, scope (module/class/import), status (skipped/error),
  affected_ids y reason/traceback segun corresponda. Conservar la distincion
  entre skip de caso y omision por fixture; no acreditar esta ultima como PASS.
- executed_ids y fixture_omitted_ids son disjuntos y su union es expected_ids.
  tests_run cuenta solo callbacks startTest. Las omisiones requieren resultado
  de fixture y alcance coherente con el inventario descubierto, no basta listar IDs.
- En workers 1 y mayores, SkipTest de setUpClass, setUpModule o import conserva
  exito/omision de unittest. Un error de fixture o teardown conserva FAIL.
- load_tests en modulo/paquete conserva FunctionTestCase, orden y hooks, workers
  1..8; comparar descubrimiento del worker con el plan y fallar ante divergencia.

## Invariants
Cumplir [evidencia completa](../ci-audit-remediation.md). Suite vacia, abortos,
duplicados, IDs ajenos, omisiones inventadas/inconsistentes y reporte ausente
siguen fallando. Un error de importacion no se transforma en skip. Subtests y
expectedFailure conservan resultados anteriores. No reducir workers en silencio
para ocultar una suite que no se pudo reconstruir.

## Examples
- Dos casos bloqueados por setUpClass SkipTest: tests_run=0, executed_ids vacio,
  dos IDs omitidos y un resultado de fixture con motivo; exit0.
- load_tests devuelve FunctionTestCase: el callback se ejecuta una vez por
  invocacion, tambien con workers4; su id no se interpreta como modulo importable.
- setUpModule RuntimeError: error y exit no cero, aunque no ejecute casos.

## Do / Don't
- DO: cotejar comportamiento con unittest independiente usando procesos reales.
- DON'T: completar executed_ids con casos no ejecutados ni aceptar skips ajenos.

## Tests
tests/test_ci_unittest_fixtures.py prueba skips por alcance, clase vecina activa,
errores de setup/teardown, load_tests en paquete/modulo, segunda pasada real y
mutaciones de reportes. El oraculo anterior sigue ejecutandose sin perder casos.

## Constraints
PARAR y reportar si se requiere quitar aserciones o filtrar casos existentes.
Solo stdlib, sin skips nuevos como optimizacion. Budgets declarativos sin Nivel2.
