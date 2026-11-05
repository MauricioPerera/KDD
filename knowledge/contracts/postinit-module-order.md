---
type: 'Task Contract'
title: 'Prioridades medidas del post-init Windows'
description: 'Usar datos de coste para reducir la cola final del post-init sin alterar Ubuntu ni casos.'
tags: ['bootstrap', 'ci', 'performance', 'integration']
task: postinit-module-order
intent: 'Aplicar un orden medido de modulos solo al post-init Windows.'
target: scripts/init_post_apply_suite.py
signature: 'python scripts/init_post_apply_suite.py --repo-root DIR [--report-json FILE]'
test_command: 'python -m unittest tests.test_ci_module_order'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_ci_module_order.py
tests_sha256: 'b7b326b45d6698305576fbcb8f70d18d024b7f4aa5a7fced79d4b5b6e98b0e8e'
touch_only: ['scripts/init_post_apply_suite.py', 'tools/ci/postinit-module-order.json']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [priorizacion medida](../postinit-module-order.md) mediante el
[orden opt-in](ci-module-order.md), conservando el [perfil nativo](init-post-apply-profile.md).

## Interface
Windows agrega --module-order con la ruta de tools/ci/postinit-module-order.json
relativa a la instalacion del lanzador, cuando ese archivo existe. Ubuntu
conserva cuatro workers y el orden original. Windows conserva ocho workers.
Una instalacion sin el archivo opcional conserva la suite completa y su orden
original; un perfil existente invalido falla, sin fallback silencioso.

## Invariants
- El archivo inicial usa el orden de costes medidos de f993e5e; sus entradas
  son orientativas y no controlan el discovery. Nuevos modulos siguen corriendo.
- La inicializacion conserva sus bytes y la copia sin .git puede ejecutar la
  suite real. No depender de tests/test_init_project.py, retirado en esa copia.
- Conservar cwd, exit del hijo, reporte nuevo, todos los casos y los SKIP
  aplicables. No cambiar entornos, espera, oraculos, limites ni las dos suites
  generales. No reutilizar cierres o resultados entre invocaciones.
- La simulacion no acredita rendimiento: comprobar el comando completo y
  despues tres workflows completos del mismo head bajo 480 s en Windows.

## Examples
- Perfil presente y valido -> priorizar coincidencias; ejecutar todos los jobs.
- Perfil ausente -> orden original con todos los casos; perfil invalido -> fallo.
- Proyecto inicializado sin .git -> datos conservados y procesos reales.

## Do / Don't
- DO conservar los fallos y cada muestra con su run, intento y SHA exactos.
- DON'T declarar cumplidos 480 s por la simulacion o por un unico PASS.

## Tests
El mismo oraculo integra el lanzador real, bootstrap real sobre un template
sintetico independiente y los procesos del runner; no ejecuta mocks del producto.

## Constraints
PARAR y reportar si se requieren cambios de runtime sin revision final o de protecciones.
La publicacion debe conservar commits y entradas del registro de aprobaciones.
