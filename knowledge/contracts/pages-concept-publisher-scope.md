---
type: 'Task Contract'
title: "Entrega de conceptos bajo el prefijo de Pages"
description: "Mantener los enlaces y hashes de la herramienta get_concept dentro del scope del publicador."
tags: ['audit', 'integration', 'quality']
task: pages-concept-publisher-scope
intent: "Resolver los conceptos publicados dentro de /KDD/ antes de calcular las huellas del bundle."
target: site/build.py
signature: "def scope_generated_concept(output)"
test_command: "python -m unittest tests.test_pages_concept_delivery"
test_runner: python-unittest
oracle_files: ["tests/test_pages_concept_delivery.py", "site/package-lock.json"]
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_pages_concept_delivery.py"
tests_sha256: '9da57a6f076a115e225c29288a07b83bb97e3b550285273f890e18c2db4921db'
touch_only: ["site/build.py", "site/llms-skills.json"]
deps_allowed: ["node", "llms-skills"]
forbids: ['llm']
---

## Intent
Resolver conceptos bajo /KDD/ antes de publicar.

## Interface
El build adapta get_concept y advierte truncamiento mediante error.

## Invariants
Mantener las huellas sobre bytes finales, limite de memoria y scope.

## Examples
- El concepto corto llega completo.
- El cuerpo truncado devuelve error explicito.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
Node y HTTP local. Comprobar el orden del build con un fixture del publisher.
Ejecutar el build fijado y MCPWASM para verificar la entrega.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
