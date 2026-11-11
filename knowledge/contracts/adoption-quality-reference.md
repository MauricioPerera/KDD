---
type: 'Task Contract'
title: 'Resolver la política del complemento desde la referencia aprobada'
description: 'Impedir que el candidato desactive una política de calidad aprobada.'
tags: ['adoption', 'quality', 'git']
task: adoption-quality-reference
intent: 'Anclar la selección de la política de calidad a un commit del consumidor.'
target: tools/kdd-adoption/validate.py
language: python
signature: 'def quality_check(validator):'
test_command: 'python -m unittest tests/test_adoption_quality_reference.py'
test_runner: python-unittest
oracle_files: ['tests/test_adoption_quality_reference.py', 'tests/adoption_remediation_support.py', 'tests/test_adopt_project.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt', 'scripts/validate_contracts.py', 'scripts/validate_okf.py', 'scripts/validate_test_commands.py', 'scripts/validate_baseline.py', 'scripts/verify_quality.py', 'scripts/oracle_execution.py', 'scripts/oracle_inventory.py', 'scripts/validation_runtime.py', 'scripts/process_tree.py', 'scripts/unittest_oracle_runner.py']
budget:
  cyclomatic_max: 12
  nesting_max: 3
tests: tests/test_adoption_quality_reference.py
tests_sha256: 'bdb3d4d153ea9c82874747489b0fca54ca4fb066c050a59ec3a57118d81d6582'
touch_only: ['tools/kdd-adoption/validate.py', 'tools/kdd-adoption/README.md']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Preservar la [aprobación de calidad](../quality-approval.md) al adoptar el
[complemento](../piloto-kdd-complemento.md).

## Interface

`python .kdd/validate.py` recibe `KDD_QUALITY_APPROVED_REF`, un SHA completo
de un commit del consumidor. Con la referencia configurada, el lanzador busca
una sola política regular entre `quality/product.json` y `quality.json` en
ese commit. Registra la referencia efectiva en `KDD_PILOT` tras aprobarla.

## Invariants

- Una referencia inválida o inaccesible, una política ausente, no regular o
  ambigua y la desaparición o sustitución de la política en el candidato
  fallan en `quality` antes de ejecutar el oráculo. Git ignora reemplazos.
- El verificador fijado conserva sus dos pasadas y la protección del perímetro.
  Un borrado en el índice, directorio de trabajo o commit se rechaza incluso
  cuando los tests de producto todavía pasan o el índice y el checkout
  recuperan los bytes aprobados tras un borrado confirmado.
- Sin referencia de calidad, una política detectada en el checkout, su HEAD
  o la referencia aprobada de adopción exige aprobación de calidad. Un
  consumidor sin política puede usar el flujo piloto.
- Una referencia histórica que carece de un helper obligatorio mantiene el
  rechazo. La guía indica cómo revisar y registrar un nuevo commit con política,
  oráculos, helpers e inventario, antes de actualizar la variable externa.

## Examples

- Borrar y confirmar `quality/product.json` → fallo en `quality`.
- Validar un producto intacto con su referencia aprobada → dos pasadas de
  calidad y referencia efectiva en la evidencia.

## Do / Don't

- DO reutilizar `verify_quality.py` del SHA fijado.
- DON'T inferir la activación de calidad solo de los archivos candidatos.

## Tests

Git y Python reales con políticas de ambos nombres, control positivo,
borrado staged y confirmado, referencia sin política y dos nombres aprobados.

## Constraints

La referencia aprobada y los oráculos pertenecen al consumidor. Las pruebas
usan transporte Git local y no publican datos.
PARAR y reportar si se necesita registrar una aprobación del consumidor.
