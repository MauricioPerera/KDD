---
type: 'Task Contract'
title: 'Identidad del metodo enlazado por unittest'
description: 'Distingue metodos Python distintos aunque load_tests los exponga con la misma etiqueta.'
tags: ['adoption', 'oracle', 'integration']
task: adoption-bound-method-identity
intent: 'Evitar aprobar dos pasadas con el mismo nombre y distintas definiciones Python.'
target: scripts/unittest_oracle_runner.py
signature: 'def startTest(self, test):'
test_command: 'python -m unittest tests/test_adoption_bound_method_identity.py'
test_runner: python-unittest
test_scope: infrastructure
test_timeout: 180
budget:
  cyclomatic_max: 10
  nesting_max: 3
tests: tests/test_adoption_bound_method_identity.py
tests_sha256: 'f6b35a5186bc6565e1c9930764c1ff9bd62e52e062c08ecfc7b3bb1c56892a34'
oracle_files: ['tests/test_adoption_bound_method_identity.py', 'tests/test_adoption_oracle_pass_identity.py', 'tests/test_adoption_trusted_pr.py', 'tests/adoption_remediation_support.py', 'tests/test_adopt_project.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt']
touch_only: ['scripts/unittest_oracle_runner.py', 'tools/kdd-adoption/validate.py']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Cerrar la variante de [identidad adversarial](adoption-adversarial.md) donde
`load_tests` enlaza dos definiciones a la misma etiqueta de unittest.

## Interface

El [comprobante de cada pasada](adoption-oracle-pass-identity.md) conserva
su estructura JSON. Cada ID interno incluye la etiqueta de unittest y
una huella determinista de la definicion Python enlazada. El lanzador
valida la huella y compara la identidad completa por contrato. El campo
publico `oracle_inventory` conserva las etiquetas de unittest por
contrato. El error de una pasada no acredita un inventario.

## Invariants

- Dos funciones de prueba distintas con la misma etiqueta deben divergir,
  aunque tengan el mismo nombre cualificado y ambas terminen en verde.
  La huella incluye el origen, la posicion y el codigo de la definicion
  enlazada. Registrarla al invocar el metodo que unittest ha resuelto.
  Incluir las definiciones de la cadena declarada por decoradores Python
  con __wrapped__. Evitar IDs de objetos y rutas absolutas del checkout.
- Una clase recreada por `load_tests` que enlaza la misma definicion en
  las dos pasadas conserva su veredicto y etiqueta. Se preservan los
  controles de duplicados, aislamiento por contrato y ejecucion sin
  omisiones.
- Un comprobante que solo aporta etiquetas carece de evidencia del
  metodo enlazado. El lanzador nuevo lo rechaza con un diagnostico de
  evidencia. El recorder de conteos y la instalacion historica mantienen
  su interfaz.
- La huella identifica la definicion. El estado capturado por closures,
  el resultado de las aserciones y la integridad del proceso siguen bajo
  el limite de confianza de [ejecucion de oraculos](oracle-execution.md).

## Examples

- Dos metodos enlazados al mismo atributo en clases recreadas → exit 1.
- Dos definiciones en la misma clase y con el mismo nombre → exit 1.
- La misma definicion en clases recreadas en ambas pasadas → exit 0.

## Do / Don't

- DO comparar evidencia de la definicion enlazada por unittest.
- DON'T atribuir al nombre del caso la identidad de una definicion.

## Tests

Git y Python reales con el paso generado de Actions, el lanzador
instalado y centinelas de ambas ejecuciones. El control positivo tambien
pasa por terminal. Una variante retira la huella de los comprobantes
despues de una ejecucion correcta.

## Constraints

PARAR y reportar si se requiere alterar un oraculo previo o el runtime
oficial. La publicacion revisa por separado el baseline de oraculos y
las [rutas protegidas](trusted-ci-change-review.md) del arbol candidato.
