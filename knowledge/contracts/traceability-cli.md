---
type: 'Task Contract'
title: 'Consultar trazabilidad e integrarla en calidad de producto'
description: 'Exponer JSON y matriz Markdown con cierre estricto mediante el verificador de calidad existente.'
tags: ['requirements', 'traceability', 'cli', 'integration']
task: traceability-cli
intent: 'Permitir que personas y CI consulten y exijan la trazabilidad vigente de un proyecto.'
target: scripts/traceability.py
language: python
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests/test_traceability_cli.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 120
  params_max: 5
tests: tests/test_traceability_cli.py
tests_sha256: 'fca303704aefbe8ec256ae52c7c499d7c0f6bf1e40ad0a7a26d88bdd11f85ed4'
touch_only: ['scripts/traceability.py', 'scripts/traceability_git.py', 'templates/PRODUCT-SPEC.md', 'examples/traceability/README.md', 'examples/traceability/traceability.json']
deps_allowed: ['stdlib', 'traceability_git', 'traceability_model']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Operar el [modelo](../data_models/requirement-trace.md) e integrar su
comprobacion con [quality/product.json](../quality-approval.md).

## Interface

CLI de solo lectura con --repo-root, --ref, --manifest, --format y
--require-verified. JSON y Markdown salen del mismo reporte. stdout es el
artefacto; el llamador decide donde guardarlo. Codigos 0, 1 y 2 segun el modelo.

## Invariants

Pendiente y desfasado nunca habilitan un cierre estricto. Falta de manifiesto
es un error, no SKIP. La receta protege todas las dependencias del verificador
y conserva los checks propios y las dos pasadas de verify_quality.
No cambia los 19 gates, Ubuntu/Windows ni las dos pasadas de la suite general.

## Examples

- Proyecto nuevo con tarea terminada: JSON y matriz incluyen el mismo SHA.
- Plan pendiente: consulta valida, complete=false; cierre estricto falla.
- Invocacion desde otra carpeta o rama: consulta main sin cambiar checkout.
- Check de producto: la trazabilidad desfasada impide aprobar calidad.

## Do / Don't

- DO: documentar una especificacion breve y el check exacto para CI.
- DON'T: inferir que el reporte autentica una aprobacion humana o un run remoto.

## Tests

tests/test_traceability_cli.py ejecuta procesos reales y verify_quality sobre
un proyecto nuevo. Comprueba integridad antes/despues y la receta completa.
El fixture comun esta sellado por traceability-model; no se agregan skips.

## Constraints

PARAR y reportar si se necesita cambiar scripts existentes, Board, workflows,
runtime o protecciones.
Las pruebas y el baseline requieren revision segun quality-approval antes de
implementar.
