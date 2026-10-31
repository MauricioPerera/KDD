---
type: 'Task Contract'
title: 'Controles requeridos de oraculos en la aprobacion de producto'
description: 'Ejecutar estructura soportada y contramuestras exactas revisadas desde la politica aprobada, con controles sanos y evidencia dos veces.'
tags: ['quality', 'oracles', 'governance']
task: quality-oracle-reviews
intent: 'Exigir la revision de oraculos declarada sin degradar sus fallos o ausencia de soporte.'
target: scripts/verify_quality.py
signature: 'def approve(root, policy_path, reference):'
test_command: 'python -m unittest tests.test_quality_oracle_reviews'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_quality_oracle_reviews.py
tests_sha256: '4850b57780a70fe9af31b27c7e06a52313573de125bd865dd021af2f77f9b7d1'
touch_only: ['scripts/verify_quality.py', 'scripts/mutation_audit.py']
deps_allowed: ['stdlib', 'audit_seals', 'mutation_audit', 'validate_contracts', 'process_tree']
forbids: ['network', 'llm']
---

## Intent

Aplicar la [garantia revisada de oraculos](../oracle-assurance.md), conservando
la [aprobacion de calidad](../quality-approval.md) y el
[objetivo de gobierno](../kdd-governance-closure.md).

## Interface

Agregar oracle_reviews a la politica aprobada, combinable con generated_task_evidence.
La API approve y los permisos anteriores se conservan. La rutina compartida
review_contract(contract_path, repo_root, review) vive en mutation_audit.py.

## Invariants

- Cada entrada requerida sigue el esquema exacto canonico; no acepta lista vacia,
  ID duplicado, riesgo vacio, caso esperado vacio, rutas ambiguas o fuente no congelada.
- Contrato completo, oraculo, fuentes mutantes y los cuatro modulos del runner
  quedan protegidos. El runner se extrae de Git aprobado, fuera del checkout.
- Estructura Python AST y unittest exacto son el soporte inicial. Un metodo,
  lenguaje o invocacion requeridos sin soporte bloquean, nunca SKIP como PASS.
- Estructura falla antes del primer oraculo. Original/copia realmente sanos
  preceden las contramuestras fijadas por la persona revisora.
- Solo DETECTED por los casos esperados y sin errores permite aprobar. Superviviente,
  fallo inesperado, importacion rota o control inconcluso bloquean con causa propia.
- Ejecutar cada revision dos veces, antes de los checks ordinarios de esa pasada.
  Recomprobar integridad/perimetro despues de cada revision aun si falla.
- Emitir ORACLE_REVIEW JSON por revision con iteracion, approved_ref, riesgo,
  hash del contrato, metodo estructural, controles y evidencia real de mutantes.
- Politica antigua sin oracle_reviews conserva checks y declara expresamente
  'oracle assurance not requested'; no afirma fuerza ni revision realizada.
- No modificar el auditor advisory, GATE_SPECS, Task v1 ni su bundle de cinco modulos.

## Examples

- Contramuestra congelada acepta dos; el caso esperado la rechaza -> recibo 2x.
- Sin aserciones, superviviente, fallo de importacion o metodo no soportado -> rechazo.
- Se modifica una fuente congelada durante una prueba -> integridad rechaza.

## Do / Don't

- DO aplicar la politica inmutable y reutilizar audit_seals sin alterar su default.
- DON'T inventar casos por etiqueta adversarial ni prometer generalizacion.

## Tests

Nuevo oraculo tests/test_quality_oracle_reviews.py con Git y unittest reales,
politicas sinteticas revisadas y fuentes mutantes exactas. Reutiliza los fixtures
anteriores sin editarlos; conserva los casos de compatibilidad y advisory.

## Constraints

PARAR y reportar si requiere otro archivo de produccion, oraculo anterior,
aumentar budgets o cambiar workflows/protecciones. La extension de politica
se revisa aqui; el bundle historico de tareas no se amplia. No implementar
antes de aprobar el baseline humano ni antes del CI dual-OS 2x de KG-2.
