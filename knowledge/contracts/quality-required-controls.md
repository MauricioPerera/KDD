---
type: 'Task Contract'
title: 'Restricciones requeridas en la aprobacion de producto'
description: 'Bloquear controles obligatorios sin soporte y conservar metodo, alcance y evidencia observada.'
tags: ['governance', 'restrictions', 'quality']
task: quality-required-controls
intent: 'Bloquear controles obligatorios sin soporte y conservar metodo, alcance y evidencia observada.'
target: scripts/verify_quality.py
signature: 'def approve(root, policy_path, reference):'
test_command: 'python -m unittest tests.test_required_product_controls'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_required_product_controls.py
tests_sha256: '576709f1196b9b4d9273b98b40f57e22ae4d07cfd024baca8dbf1f8bb81c67b4'
touch_only: ['scripts/verify_quality.py', 'scripts/validate_budgets.py']
deps_allowed: ['stdlib', 'validate_contracts', 'validate_budgets', 'process_tree']
forbids: ['network', 'llm']
---

## Intent

Aplicar los [controles requeridos](../required-controls.md), conservando la
[aprobacion](../quality-approval.md), la [garantia de oraculos](../oracle-assurance.md)
y el [objetivo](../kdd-governance-closure.md).

## Interface

Conservar approve, politica previa y oracle_reviews. Agregar required_controls
segun el esquema canonico. Cada entrada declarada es obligatoria y se informa
como REQUIRED_CONTROL JSON por pasada, antes de los checks de esa pasada.

## Invariants

- Politica desde Git aprobado; inventario requerido no vacio y esquema exacto.
- Contrato completo aprobado, limites originales y runner de medicion protegidos.
  Extraer validate_budgets/validate_contracts de Git regular a un bundle externo.
- Exceso medido, ausencia/error/timeout o soporte faltante bloquean; un scan de
  imports sin findings o FORBID_UNVERIFIED no satisface prohibiciones de runtime.
- Budget Python AST mide module-functions. No hay aislamiento de red/subprocess/llm
  en este perfil: requerirlo produce CONTROL_UNSUPPORTED, nunca PASS de sandbox.
- Ejecutar controles dos veces y comprobar integridad/perimetro despues de cada
  uno aun si falla, antes de oracle_reviews/checks ordinarios de esa pasada.
- REQUIRED_CONTROL incluye id, iteracion, status, mecanismo, scope, cobertura
  medida, identidades, resultados y runtime_isolation=false cuando corresponda.
- Los targets medidos conservan la misma version a traves de controles, checks
  y pasadas; un cambio posterior observado bloquea con CONTROL_CHANGED.
- Listas ausentes en legacy no acreditan restricciones efectivas; informar el limite.
- oracle_reviews y required_controls pueden coexistir sin desactivar ninguno.
- No editar audit_forbids ni promoverlo a GATE_SPECS; preservar su modo advisory.

## Examples

- Budget requerido y soportado -> medidas reales 2x; sus checks ordinarios 2x.
- Network runtime requerido sin mecanismo -> CONTROL_UNSUPPORTED antes de checks.
- Candidato eleva limite o altera runner -> rechazo de integridad, sin aprobar.

## Do / Don't

- DO conservar entradas aprobadas, limites y evidencia de cobertura.
- DON'T convertir omision, fallo o falta de soporte en una garantia positiva.

## Tests

Nuevo tests/test_required_product_controls.py usa el fixture congelado de KG-3,
Git real y el punto approve real. No cambia un test, helper u oraculo anterior.

## Constraints

PARAR y reportar si requiere otra fuente, dependencia, oraculo, mas presupuesto,
cambiar Task v1 o el bundle historico de cinco modulos. Politica y controles se
aprueban antes de implementar; no comenzar antes del CI dual-OS 2x de KG-3.
