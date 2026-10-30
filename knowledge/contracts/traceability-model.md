---
type: 'Task Contract'
title: 'Validar el modelo de trazabilidad de requisitos'
description: 'Convertir un spec breve y bindings JSON estrictos en relaciones canonicas con huellas estables.'
tags: ['requirements', 'traceability', 'schema']
task: traceability-model
intent: 'Definir una unica fuente de requisitos y rechazar relaciones ambiguas antes de derivar evidencia.'
target: scripts/traceability_model.py
language: python
signature: 'def parse_plan(spec_text, manifest_text):'
test_command: 'python -m unittest tests/test_traceability_model.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 120
  params_max: 5
tests: tests/test_traceability_model.py
tests_sha256: '8d884b9a439111f0255a6eb0837945c718e0baaeed03c1af6131f9c953125abe'
touch_only: ['scripts/traceability_model.py']
deps_allowed: ['stdlib', 'validate_contracts']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Aplicar el [modelo v1](../data_models/requirement-trace.md) a la
[especificacion breve](../traceability-product-spec.md), sin inferencia semantica.

## Interface

parse_plan recibe ambos textos UTF-8 y devuelve spec y requirements canonicos.
Cada requisito expone id, text, bindings y fingerprint, segun el modelo.
Errores de esquema levantan ValueError con prefijo TRACE_SCHEMA o TRACE_SPEC.

## Invariants

Claves, tipos, IDs, rutas, totalidad de enlaces y asignaciones se validan.
No se ejecuta codigo ni se lee filesystem. La huella es estable ante reordenar
JSON y cambia al modificar el requisito o cualquiera de sus enlaces propios.

## Examples

- Dos requisitos enlazados al mismo contrato son validos.
- Requisito sin binding o ID duplicado se rechaza.
- tasks vacio se conserva como plan pendiente, nunca como prueba verificada.
- Agregar un requisito ajeno conserva la huella de los anteriores.

## Do / Don't

- DO: reutilizar el parser canonico de frontmatter.
- DON'T: aceptar campos manuales complete, passed o verified como evidencia.

## Tests

tests/test_traceability_model.py incluye los controles de esquema y el fixture
Git real compartido por los dos oraculos de integracion. El sello cubre todo
ese helper; no hay una dependencia de prueba nueva sin proteger.

## Constraints

Sin cambiar oraculos anteriores ni el dialecto OKF. Baseline revisado antes de
implementar segun [quality-approval](../quality-approval.md).
PARAR y reportar si se requiere cambiar un oraculo anterior o la sintaxis OKF.
