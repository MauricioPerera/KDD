---
type: 'Task Contract'
title: 'Contador de Pages ligado al inventario real del CI'
description: 'Exportar y cotejar IDs de las cuatro pasadas y abortar ante discovery incompleto antes de producir el bundle.'
tags: ['ci', 'pages', 'integration']
task: pages-inventory
intent: 'Impedir cifras parciales o de otro run, intento o commit en la pagina publica.'
target: site/ci_inventory.py
language: python
signature: 'def inspect_inventory(repo_root, ci_run_url, ci_inventory=None):'
test_command: 'python -m unittest tests/test_pages_inventory.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
tests: tests/test_pages_inventory.py
tests_sha256: '65072b6a38464cb7e4e43ce2b17b85ac4a87b3988b53551d5920b83a0ae3890c'
touch_only: ['site/ci_inventory.py', 'site/build.py', 'site/index.html']
deps_allowed: ['stdlib', 'Git', 'Node.js', '@rckflr/llms-skills@0.4.1']
forbids: ['llm']
---

## Intent
Aplicar la [procedencia e invariantes](../pages-ci-inventory.md) al
[build](pages-build.md), preservando el [runner](ci-suite-processes.md).

## Interface
- inspect_inventory devuelve ids, ids_sha256, tests e inventory_source.
- CLI inspect: --repo-root DIR --ci-run-url URL; preview por defecto.
  --ci-inventory-dir DIR --ci-run-attempt N --ci-trusted-runtime-ref SHA son
  opcionales como grupo completo para verificar evidencia de CI.
- CLI export: --repo-root DIR --reports-dir DIR --output FILE --run-id N
  --run-attempt N --head-sha SHA --platform SO --trusted-runtime-ref SHA.
- build_pages conserva sus tres argumentos y agrega keyword ci_inventory=None;
  su CLI admite el mismo grupo opcional. Devuelve tambien ids_sha256 e
  inventory_source sin quitar los campos anteriores.
- Fallos diagnosticos PAGES_DISCOVERY o PAGES_CI_INVENTORY y exit no cero.

## Invariants
Cumplir el [protocolo](../pages-ci-inventory.md), incluido el esquema v1,
igualdad de IDs, cuatro reportes distintos, identidad exacta y aborto antes
del output. Sin fallback ni ejecucion de casos para contar. Conservar los
skips contabilizados por el runner; no presentar inventario como cobertura.
Mantener las seis fuentes del runtime revisado y sus validadores intactas.

## Examples
- Dos reportes reales por SO, identidad e IDs coincidentes: ci-verified.
- Import faltante o syntax/load_tests roto: PAGES_DISCOVERY sin bundle.
- Mismo numero pero distintos IDs, runtime o intento: PAGES_CI_INVENTORY.
- PR sano sin artifacts finales: discovery-preview, sin publicar.

## Do / Don't
- DO: subprocess nuevo, UTF-8 explicito y Git/runner reales en integracion.
- DON'T: contar _FailedTest, inferir aprobaciones de HEAD ni ignorar errors.

## Tests
tests/test_pages_inventory.py cubre discovery, export de reportes reales,
consenso, identidad, replay, corrupcion, CLI y aborto del build real antes
de crear output. Los controles del publisher completo corresponden al
workflow real; no se declaran ejecutados si solo corrio un probe de inventario.

## Constraints
Baseline humano explicito antes de implementar. PARAR y reportar si se
necesita cambiar runtime, oraculos fuera del diff revisado o protecciones.
Budget declarativo; sin afirmacion de Nivel2, firma ni sandbox.
