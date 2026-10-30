---
type: 'Task Contract'
title: 'Transportar inventarios del run exacto entre CI y Pages'
description: 'Exportar despues de ambas suites, descargar ambos SO del evento y exigir discovery y evidencia completos antes de publicar.'
tags: ['ci', 'pages', 'workflow']
task: pages-inventory-ci
intent: 'Vincular la cifra publica al CI terminado del mismo commit conservando las matrices y las dos pasadas.'
target: .github/workflows/deploy-pages.yml
language: yaml
signature: 'validate_and_publish_pages_ci_inventory(workflow_run)'
test_command: 'python -m unittest tests/test_pages_inventory_ci.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_pages_inventory_ci.py
tests_sha256: '63fd48e338daf1cb4eb8bba366d66aacd9e5017b0740f95a8b32430a6c32139a'
touch_only: ['.github/workflows/deploy-pages.yml', '.github/workflows/validate.yml']
deps_allowed: ['GitHub Actions', 'Python3.11', 'Node24', 'Git']
forbids: ['llm']
---

## Intent
Conectar el [protocolo](../pages-ci-inventory.md) al
[build en PR](pages-pr-build.md) y al [build publico](pages-build.md).

## Interface
En validate: Export Pages CI inventory y Upload Pages CI inventory, despues
de Run unit tests (2/2), solo push nativo de main. El export usa los reportes
reales y github.run_id/run_attempt/sha, matrix.os y KDD_TRUSTED_RUNTIME_REF.
Pages agrega Install pinned discovery parsers, Download Ubuntu CI inventory
y Download Windows CI inventory antes de Build and validate public bundle.
El build recibe directorio de ambos manifests, intento y runtime explicitos.

## Invariants
Cumplir [procedencia, pins y permisos](../pages-ci-inventory.md). Mantener
cuatro jobs, dos matrices Ubuntu/Windows, dos comandos identicos de suite,
Python3.11, Node24 y los 19 gates. Sin cambios a trusted-pr-gate, runtime o
protecciones; sin permissions write adicionales ni despliegue desde PR.
El unico permiso nuevo en deploy es actions:read. Descargar manifests JSON,
nunca HTML, codigo ejecutable ni artifacts de otro run/intento.

## Examples
- Main exitoso con cuatro reportes exportados: build y despliegue coherentes.
- Un artifact falta, expira o no valida su digest: abortar antes del build/upload.
- Consumidor reusable o PR: no export/upload nativo; el PR conserva preview.

## Do / Don't
- DO: nombres exactos ligados al evento, dos destinos separados y SHA completo.
- DON'T: seleccionar run-id: latest, merge-multiple, patrones, permisos write
  o continue-on-error. Los nombres de SO ubuntu-latest/windows-latest son validos.

## Tests
tests/test_pages_inventory_ci.py comprueba cableado, procedencia, pins,
instalacion de parsers, argumentos del build y preservacion de la matriz.
La [integracion real](pages-inventory.md) verifica el comportamiento con
reportes reales; la ejecucion remota queda pendiente hasta ser autorizada.

## Constraints
Baseline humano antes de implementar. No autoriza publicar, fusionar ni
cambiar protecciones. Los pins se revisaron en repositorios oficiales.
PARAR y reportar si se necesita otro permiso, runtime u oraculo fuera de
la propuesta revisada, o modificar una proteccion remota.
