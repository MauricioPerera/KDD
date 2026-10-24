---
type: 'Task Contract'
title: 'CI de calidad de producto al inicializar'
description: 'Adaptar el workflow de proyectos nuevos para exigir calidad de producto con referencia revisada y runner congelado.'
tags: ['bootstrap', 'quality', 'integration']
task: bootstrap-product-quality-ci
intent: 'Evitar SKIP de calidad en el CI de un proyecto nuevo sin aprobar automaticamente sus oraculos.'
target: scripts/init_project.py
language: python
signature: 'def init_project(repo_dir, apply, name, repository=None) -> dict:'
test_command: 'python -m unittest tests/test_bootstrap_product_quality_ci.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_bootstrap_product_quality_ci.py
tests_sha256: 'c1d4d1f3411bf0f2595a93eda7faf2d28fdb61cdc6994da70cfb82e05f3ee955'
touch_only: ['scripts/init_project.py', 'scripts/bootstrap_project.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent
Aplicar [calidad desde el arranque](../bootstrap-product-quality-ci.md)
mediante las dos entradas existentes, conservando el
[contrato de inicializacion](init-project.md), el
[bootstrap](bootstrap-project.md) y la [aprobacion independiente](../quality-approval.md).

## Interface
- Firmas, argumentos posicionales, perfiles y exit codes existentes.
- Resultado agrega quality_ci_configured: false en dry-run y true en apply.
- init prepara el workflow antes de borrar y solo lo escribe en apply.
- bootstrap delega esa adaptacion y explica politica y ambas variables.

## Invariants
- Ninguna escritura en dry-run ni ante identidad/manifiesto/workflow
  ausente o estructura ambigua. Admitir LF/CRLF conservando su formato.
- Cambiar solo las regiones de calidad del workflow de la copia:
  defaults quality/product.json y quality, referencia explicita en el job,
  precondicion anterior a oraculos y ejecucion mediante runner aprobado.
- El CI generado exige archivo, SHA completo existente y ancestro de HEAD.
  Sin configuracion falla; no deduce aprobacion de HEAD, main ni upstream.
- Runner extraido por git show del SHA aprobado a temporal externo y
  aplicado al checkout/indice completo. Rechazar runner, politica, oraculo
  o workflow alterado y archivos fuera del perimetro antes de aprobar.
- Conservar gates, validacion de tareas, baseline, matriz Ubuntu/Windows,
  concurrencia, deduplicacion y las dos pasadas de la suite.
- No generar politica de producto con checks ficticios ni modificar una
  existente. El equipo define su producto y el revisor registra el SHA.
- La guia conserva el comando minimal sin --approved-ref; la preparacion
  obligatoria del CI se explica mediante las variables para todos los perfiles.
- El workflow de KDD, oraculos anteriores y sus sellos quedan intactos.

## Examples
- Copia integra -> bootstrap/init -> CI requiere quality/product.json.
- Configuracion ausente -> FAIL; producto y referencia revisados -> PASS
  real de checks funcionales/adversariales/CLI 2x y resumen PASS de quality.
- Runner candidato finge PASS -> rechazo por el runner aprobado.
- Workflow de entrada modificado de forma incompatible -> exit 2 sin borrar.

## Do / Don't
- DO usar Git propio y procesos reales en temporales, sin red.
- DO probar APIs, CLIs, guia, errores previos a limpieza y mutaciones.
- DON'T copiar tareas, rutas de producto o SHAs de la demostracion.

## Tests
tests/test_bootstrap_product_quality_ci.py inicializa copias de la plantilla,
crea producto/oraculo/politica propios y ejecuta los cuerpos Python reales
del workflow generado. Verifica PASS y rechazos efectivos, no solo texto.
Los casos de instanciacion se omiten en copias ya inicializadas para evitar
recursion; se ejecutan completos en KDD. El fixture no aprueba el repo real.

## Constraints
PARAR y reportar si fuera necesario modificar oraculos anteriores o elegir
una referencia aprobada en nombre del revisor.
Stdlib, sin subprocess ni red en el inicializador; esos nombres solo
aparecen como texto del workflow generado. No cambiar las protecciones ni
variables remotas. El budget es declarativo sin gate de Nivel 2.
