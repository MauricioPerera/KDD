---
type: 'Task Contract'
title: 'Evidencia adversarial de la adopcion'
description: 'Comprueba la identidad de la revision, los casos ejecutados y el checkout al cierre de la adopcion.'
tags: ['adoption', 'review', 'oracle', 'security']
task: adoption-adversarial
intent: 'Detectar falsos verdes en la revision y la adopcion aprobada.'
target: tools/kdd-adoption/validate.py
signature: 'def approved_oracle_passes(validator, contracts, python, reference, directory):'
test_command: 'python -m unittest tests/test_adoption_adversarial_oracles.py tests/test_adoption_adversarial_review.py tests/test_adoption_adversarial_transport.py'
test_runner: python-unittest
test_scope: infrastructure
test_timeout: 300
budget:
  cyclomatic_max: 10
  nesting_max: 3
tests: tests/test_adoption_adversarial_oracles.py
tests_sha256: '25d31bbc73803f37688cd881fa66479cd2e7e053eba345ad69d50a088a3dd168'
oracle_files: ['tests/test_adoption_adversarial_oracles.py', 'tests/test_adoption_adversarial_review.py', 'tests/test_adoption_adversarial_transport.py', 'tests/test_adoption_oracle_pass_identity.py', 'tests/test_plugin_odd_egm_review.py', 'tests/test_adoption_trusted_pr.py', 'tests/adoption_remediation_support.py', 'tests/test_adopt_project.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt']
touch_only: ['tools/kdd-adoption/validate.py', 'scripts/unittest_oracle_runner.py']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Aplicar la [bateria adversarial](../../docs/reports/PLUGIN-ODD-EGM-ADVERSARIAL-PLAN.md)
a los lanzadores de [revision](plugin-odd-egm-review.md) y
[adopcion](adoption-oracle-pass-identity.md).

## Interface

La entrada `review --approved-ref SHA` requiere un SHA completo de adopcion.
La adopcion aprobada conserva el esquema de comprobantes por contrato.

## Invariants

- Una referencia de revision vacia produce exit 2. Una revision lista
  conserva el requisito independiente de aprobacion del consumidor.
- El comprobante usa la identidad del metodo de `unittest.TestCase`
  que se inicio, incluso si la clase redefine `id()`.
- Al terminar cada pasada, el lanzador vuelve a enumerar los contratos
  seleccionados y comprueba sus oraculos y los archivos administrados
  contra la adopcion aprobada. Un cambio persistente bloquea el veredicto.

## Examples

- Dos metodos distintos declaran el mismo `id()` → las pasadas divergen.
- Un contrato inmediato aparece tras el segundo comprobante → exit 1.
- Una errata confirmada con referencia aprobada → ruta ligera.

## Do / Don't

- DO comprobar el resultado, los centinelas y la etapa de rechazo.
- DON'T contar como rechazo una falla de preparacion del escenario.

## Tests

La bateria usa Git y Python reales, el lanzador instalado, el paso generado
de Actions y comprobantes adversariales controlados. Conserva los controles
positivos y las dos pasadas completas por sistema.

## Constraints

PARAR y reportar si una inyeccion requiere modificar un consumidor real.
El host, el runner y el oraculo aprobado operan dentro del limite de
confianza de [ejecucion de oraculos](oracle-execution.md). El ensayo local
de un workflow sustituido mide el paso aprobado. La identidad del check
requerido se verifica en el despliegue.
