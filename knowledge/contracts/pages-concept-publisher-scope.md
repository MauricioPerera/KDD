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
tests_sha256: 'e16b908fab6a23269311fe1247c014a3807b269b2ed7593681d05564bd6ee9f8'
touch_only: ["site/build.py", "site/llms-skills.json"]
deps_allowed: ["node", "llms-skills"]
forbids: ['llm']
---

## Intent
Resolver los conceptos publicados dentro de /KDD/ antes de calcular las huellas del bundle. El alcance sigue [inventario de Pages](../pages-ci-inventory.md).

## Interface
El build adapta el get_concept generado antes de publicar y sellar. La herramienta conserva el id de concepto, obtiene Markdown bajo /KDD/knowledge/ y devuelve error explicito si fetchOrigin informa truncamiento.

## Invariants
Conservar la respuesta completa de los documentos cortos, fallo de id desconocido sin peticion, firmas y digests sobre los bytes finales, limite de memoria y seguridad de origen. Los otros tool.js conservan su semantica.

## Examples
- Un concepto corto devuelve su Markdown completo en el montaje /KDD/.
- Un concepto que supera el limite del host produce un diagnostico de truncamiento.

## Do / Don't
- DO: reusar el punto de entrada y los controles existentes.
- DON'T: Evitar ampliar el scope del sandbox, ocultar truncamiento o elevar el limite.

## Tests
Ejecutar la herramienta JavaScript generada del fixture con Node y HTTP local, montada estrictamente en /KDD/. Ademas cotejar build real y cliente MCPWASM en ambos sistemas antes de acreditar el despliegue.

## Constraints
Aprobar el SHA del baseline antes de implementar. PARAR y reportar si se
requiere cambiar controles remotos, el runtime confiable u oraculos previos.
