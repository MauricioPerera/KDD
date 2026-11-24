---
type: 'Task Contract'
title: 'Origen aprobado del auditor de presupuestos del CI'
description: 'Ejecutar el auditor del diff desde un commit fijado por el workflow protegido.'
tags: ['quality', 'budget', 'ci']
task: changed-budget-ci-source
intent: 'Vincular el recibo del presupuesto a los bytes aprobados del auditor.'
target: .github/workflows/validate.yml
language: yaml
signature: 'audit_changed_python_budgets(validate, base_ref, head_ref)'
test_command: 'python -m unittest tests.test_changed_budget_ci_source'
test_runner: python-unittest
oracle_files: ['tests/test_changed_budget_ci_source.py', 'tests/test_changed_budget_receipt.py', 'tests/quality_review_fixture.py', 'tests/test_fixture_preparation.py']
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_changed_budget_ci_source.py
tests_sha256: '4807002250168ac42fefe12da1af82bafc8a24bf09714d6143915f74434d3190'
touch_only: ['.github/workflows/validate.yml', 'knowledge/validacion.md']
deps_allowed: ['stdlib', 'git']
forbids: ['llm', 'network']
---

## Intent

Asociar el [recibo de alcance](changed-budget-receipt.md) a un auditor reproducible
y aprobado, con los mismos objetos candidatos que exige el
[control diferencial](changed-python-budgets.md).

## Interface

El paso `Audit changed Python budgets` fija `KDD_BUDGET_AUDITOR_REF` a un
OID nativo completo y literal de un commit aprobado. Usa
`KDD_BUDGET_BASE_REF` y `KDD_BUDGET_HEAD_REF` para los insumos del diff.
El log registra una linea `BUDGET_AUDITOR ` seguida de JSON con el
`ref` exacto y `files`, mapa de ruta completa de cada modulo a SHA-256 de
sus bytes Git. El paso imprime el [recibo JSON](changed-budget-receipt.md)
del auditor y conserva su codigo de salida.

## Invariants

- El workflow protegido fija la referencia sin leerla del candidato ni
  derivarla de HEAD. Resolver exclusivamente el commit indicado, sin
  reemplazos Git, y exigir blobs regulares para
  `scripts/validate_changed_budgets.py`, `scripts/validate_budgets.py` y
  `scripts/validate_contracts.py`. Ausencia o referencia invalida falla.
- Extraer los tres modulos a un directorio temporal fuera del checkout.
  Usar el shell Python aislado para el paso y ejecutar tambien el auditor en
  modo aislado con imports del bundle y biblioteca
  estandar. El checkout candidato aporta el repositorio para las lecturas Git.
  Su ausencia de copias ejecutables del auditor no impide el control.
- Comprobar que el HEAD real del checkout es el SHA candidato solicitado.
  Preservar el alcance del workflow nativo y el comportamiento del workflow
  reutilizable. Conservar las protecciones, el runtime global y los limites
  existentes. La revision protegida del workflow corresponde al arbol final.

## Tests

Ejecutar el bloque Python real del workflow en un repositorio Git con un
commit de herramientas independiente de los objetos del diff. Comprobar
los hashes originales, el recibo y los codigos de salida con commit
aprobado ausente o invalido, archivos no regulares, reemplazos Git, imports del entorno, exceso real y
HEAD equivocado.

## Examples

- Un checkout candidato sin los scripts de medicion emite un recibo si el
  commit literal aprobado contiene los tres modulos regulares.
- Un objeto fuera del conjunto regular exigido bloquea antes del analisis.

## Do / Don't

- DO hacer visible en el log la identidad de cada modulo ejecutado.
- DON'T importar codigo candidato durante la medicion.

## Constraints

Mantener el catalogo de jobs y el runtime global. El pin del auditor se revisa
con el diff protegido del workflow y debe ser alcanzable desde el checkout
completo de CI. Crear el commit del auditor antes del que fija el workflow,
conservar ambos en la integracion y comprobar el pin en el CI del arbol final.
PARAR y reportar si hace falta cambiar el runtime global o las protecciones.
