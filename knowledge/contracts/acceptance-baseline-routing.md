---
type: 'Task Contract'
title: 'Referencia aprobada de aceptación en CI'
description: 'Vincular la comprobación de la política de aceptación con la referencia que seleccionó el job.'
tags: ['ci', 'acceptance', 'baseline']
task: acceptance-baseline-routing
intent: 'Ejecutar la aceptación contra el SHA aprobado que resolvió el selector.'
target: .github/workflows/validate.yml
language: yaml
signature: 'Select approved references -> Verify required contract acceptance'
test_command: 'python -m unittest tests.test_acceptance_baseline_routing'
test_runner: python-unittest
budget:
  cyclomatic_max: 1
  nesting_max: 1
tests: tests/test_acceptance_baseline_routing.py
tests_sha256: '08b90b2ff21339dfb0576dd874769beeecc1eae6145b9076b04985d7b2ca5ed5'
oracle_files: ['tests/test_acceptance_baseline_routing.py', 'tests/test_contract_acceptance.py', 'tests/__init__.py']
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['Python3.11', 'stdlib', 'GitHub Actions']
forbids: ['llm']
---

## Intent

El selector lee el [registro aprobado](approval-registry.md). El paso de
[aceptación](../acceptance.md) usa esa decisión para detectar una política
borrada y para verificar la entrega.

## Interface

El paso `Select approved references` exporta en `GITHUB_ENV`
`KDD_ACCEPTANCE_APPROVED_REF` con el mismo SHA que
`KDD_APPROVED_BASELINE_REF`. El paso `Verify required contract acceptance`
consume ese valor para consultar la política aprobada y para pasar
`--approved-ref` a `scripts/verify_acceptance.py`.

## Invariants

- El mismo selector resuelve registro por árbol y referencias explícitas
  del workflow reutilizable.
- Una variable global histórica, incluso con un SHA distinto, no sustituye
  la referencia elegida.
- Una política presente en el candidato o en el baseline activa la
  verificación. La opción obligatoria también la activa cuando está ausente.
- Los proyectos opcionales sin política en ambos árboles conservan
  `NOT_EVALUATED`. Los errores del verificador fallan el job.
- Conservar el guard confiable, la matriz Ubuntu/Windows, las dos pasadas y
  los oráculos existentes.

## Examples

- El registro selecciona una política que el candidato borró. La
  aceptación rechaza el borrado incluso si el input explícito está vacío.
- El registro y la variable histórica nombran commits distintos. El
  reporte identifica el SHA seleccionado por árbol.
- Una referencia explícita válida en modo reutilizable se usa también
  en la matriz de aceptación.

## Do / Don't

- Reusar el SHA resuelto por el selector para toda la comprobación.
- Mantener la activación y el resultado del verificador de aceptación.

## Tests

Las pruebas ejecutan los dos bloques reales del workflow en subprocesos
Python sobre repositorios Git descartables. Cubren el borrado de la
política, una variable global obsoleta y el modo reutilizable.

## Constraints

PARAR y reportar si falta la aprobación del baseline o la revisión
externa de la modificación protegida del workflow.
