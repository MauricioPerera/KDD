---
type: 'Task Contract'
title: 'Entrega de contexto con identidad completa'
description: 'Entrega de contexto con identidad completa con alcance mecanico y revision humana explicitos.'
tags: ['governance', 'provenance', 'verification']

task: context-delivery-manifest
intent: 'Entrega de contexto con identidad completa.'
target: scripts/assemble_context.py
signature: 'def assemble(contract, task, base_dir):'
test_command: 'python -m unittest tests.test_context_delivery_manifest'
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_context_delivery_manifest.py
tests_sha256: '5fdf50e8136e67dc2b9ed60ebd3dddbe0051b3aacdc1d8524b47c71f1e489fce'
touch_only: ['scripts/assemble_context.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Cumplir la [propuesta de contexto y aprendizaje](../context-learning-provenance.md)
y el [objetivo](../kdd-governance-closure.md), conservando la
[aprobacion](../quality-approval.md) y sus limites de confianza.

## Interface

Conservar API, CLI, formatos anteriores, presupuesto, ranking y providers.
Agregar manifest schema_version=1 con fuentes y fragmentos reales; publicar
el mismo JSON en una linea CONTEXT_MANIFEST del reporte.

## Invariants

- source_sha256 identifica texto UTF-8 LF; raw_sha256 identifica bytes fisicos.
- Spans son indices de caracteres de context, sin cabeceras; hash UTF-8 del fragmento.
- Registrar fuentes recuperadas full/truncated/omitted con rutas que desambiguen IDs.
- No inventar Git commit a partir de una lectura de archivo o de runtime.
- required booleano: ausencia, omision, corte o seleccion vacia -> CONTEXT_REQUIRED
  mediante GuardrailAbort con resultado parcial. No aumentar el presupuesto.
- expected_sha256 de static fija version de texto; formato invalido se rechaza.
- Conservar el punto _read_file y comprobar cambios persistentes observados al
  terminar; no acreditar estabilidad si la fuente requerida cambia durante lectura.
- Mantener oraculos anteriores, heuristica de tokens y cortes deterministas.

## Examples

- Texto estatico -> identidad completa y span que coincide con context.
- Nodo opcional omitido -> hash de origen, sin hash o span de entrega.
- Contexto requerido truncado, ausente o con pin obsoleto -> aborto tipado.

## Do / Don't

- DO conservar evidencia real, versiones y alcance observado.
- DON'T presentar una identidad o referencia como comprension, semantica o ejecucion.

## Tests

Oraculo nuevo tests/test_context_delivery_manifest.py con filesystem/Git reales. La extension de
inicializacion revisa unicamente las tres expectativas exactas documentadas
del oraculo anterior; los demas contratos y tests congelados se conservan.

## Constraints

PARAR y reportar si hace falta otra fuente, oraculo, dependencia, ampliar budgets,
modificar workflows/protecciones o la confianza del runner. Aprobar baseline
antes de implementar y esperar el CI dual-OS 2x de KG-4. No inferir aprobacion
humana ni certificacion retrospectiva de ejecucion o comprension.
