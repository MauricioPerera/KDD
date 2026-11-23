---
type: 'Task Contract'
title: "Entrega de conceptos bajo el prefijo de Pages"
description: "Mantener los enlaces y hashes de la herramienta get_concept dentro del scope del publicador."
tags: ['audit', 'integration', 'quality']
task: pages-concept-publisher-scope
intent: "Resolver los conceptos publicados dentro de /KDD/ antes de calcular las huellas del bundle."
target: scripts/finalize_pages_concepts.py
signature: "def finalize_pages_concepts(repo, output)"
test_command: "python -m unittest tests.test_pages_concept_delivery"
test_runner: python-unittest
oracle_files: ["tests/test_pages_concept_delivery.py", "site/package-lock.json"]
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_pages_concept_delivery.py"
tests_sha256: '01f0c8369e6a93d3d90dfb6c1a6959724f29413df979cacb3f6683593cc16625'
touch_only: ["scripts/finalize_pages_concepts.py", ".github/workflows/validate.yml", ".github/workflows/deploy-pages.yml"]
deps_allowed: ["node", "llms-skills"]
forbids: ['llm']
---

## Intent
Resolver conceptos bajo /KDD/ antes de publicar.

## Interface
Ambos workflows ejecutan el finalizador sobre su salida del build original.
El finalizador adapta get_concept, vuelve a publicar con el pin vigente y
valida las huellas finales. Un truncamiento devuelve error explicito.

## Invariants
Mantener firmas, hashes y scope del publicador. Conservar site/build.py,
inventarios, pasos del build, condiciones, permisos, limites y protecciones.

## Examples
- El concepto corto llega completo.
- El cuerpo truncado devuelve error explicito.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
Node, HTTP y build real con fixture del publisher. Comprobar orden y rutas
de ambos workflows, con el mismo artefacto final antes de usarlo.
Ejecutar el build fijado y MCPWASM para verificar la entrega.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
