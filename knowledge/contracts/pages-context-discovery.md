---
type: 'Task Contract'
title: 'Dependencias de discovery de Pages para contexto CCDD'
description: 'Preparar el discovery de Pages con las mismas dependencias fijadas que la suite de CI.'
tags: ['ci', 'pages', 'context', 'integration']
task: pages-context-discovery
intent: 'Impedir que Pages falle al importar el oraculo CCDD v0.3 durante el discovery estricto.'
target: .github/workflows/deploy-pages.yml
language: yaml
signature: 'Install pinned context compatibility dependencies'
test_command: 'python -m unittest tests.test_pages_context_discovery'
budget:
  cyclomatic_max: 1
  nesting_max: 1
tests: 'tests/test_pages_context_discovery.py'
tests_sha256: '5c67327401fed1e2fcefc01055fb9793ab8fb8de9b16d356d6d3b976f1c08e43'
touch_only: ['.github/workflows/deploy-pages.yml']
deps_allowed: ['PyYAML', 'jsonschema', 'GitHub Actions', 'Python3.11']
forbids: ['llm']
---

## Intent
Aplicar el [inventario estricto](../pages-ci-inventory.md) al oraculo del
[perfil de contexto](../context-v03-compat.md) tambien en el despliegue.

## Interface
El workflow de Pages instala incondicionalmente `tools/context-v03/requirements.txt`
con `--require-hashes --only-binary=:all:` antes del build publico. La matriz
valida el mismo lock antes de su preview y las dos suites.

## Invariants
Conservar descarga de inventarios del run exacto, discovery estricto, fallo
ante dependencias ausentes, permisos, pins, runtime y controles de confianza.
No modificar oraculos existentes ni presentar un discovery incompleto como PASS.

## Examples
- Sin PyYAML, el discovery real rechaza la importacion del oraculo de contexto.
- Con las dependencias fijadas, el discovery real incluye los IDs de contexto.
- Falta instalacion incondicional anterior al build: el contrato falla.

## Do / Don't
- DO: instalar el lock ya revisado, sin alterar hashes ni relajar sus opciones.
- DON'T: omitir pruebas, resolver el error mediante SKIP ni reducir el inventario.

## Tests
`tests/test_pages_context_discovery.py` ejecuta discovery real en procesos nuevos,
comprueba fallo sin dependencias, exito con ellas y el orden de ambos workflows.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si se necesita cambiar
protecciones o el runtime de CI.