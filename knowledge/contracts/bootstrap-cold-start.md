---
type: 'Task Contract'
title: 'Preparar dependencias del arranque local sin cache heredado'
description: 'Completar la guia con actionlint fijado y verificar una inicializacion fria con paquetes oficiales.'
tags: ['bootstrap', 'onboarding', 'integration']
task: bootstrap-cold-start
intent: 'Permitir ejecutar los controles locales despues de preparar explicitamente la herramienta revisada.'
target: scripts/bootstrap_project.py
language: python
signature: 'def _start_here(name, profile):'
test_command: 'python -m unittest tests/test_bootstrap_cold_start.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
  lines_max: 150
  params_max: 5
tests: tests/test_bootstrap_cold_start.py
tests_sha256: '824654bb82feada3e9ec52ac74a99355f8c0932f1f83435c7d73c16c945d5a46'
touch_only: ['scripts/bootstrap_project.py', 'knowledge/quickstart.md']
deps_allowed: ['stdlib', 'init_project', 'bootstrap_transaction']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Cerrar el arranque frio del [protocolo](../bootstrap-safety.md) usando el
[instalador ya revisado](workflow-syntax.md), sin cambiar perfiles ni CI.

## Interface

Quickstart y guia de los tres perfiles incluyen python scripts/validate_workflows.py
install antes de suite/perfil, y explican --archive para uso offline. No se
descarga desde bootstrap ni se selecciona una nueva version/baseline.

## Invariants

minimal sigue sin --approved-ref; standard/strict siguen requiriendolo.
Herramienta fijada por manifest existente. La prueba no hereda binario, variables
KDD_ACTIONLINT_* ni cache: usa temporales vacios y archivo oficial verificado
como dato offline. Ningun fallo de instalacion o ausencia es PASS/SKIP.
La [extension de cache del fixture](bootstrap-fixture-cache.md) conserva esas
aserciones y revisa su resolucion desde la cache predeterminada.
Workflows, 19 gates, Ubuntu/Windows y las dos pasadas permanecen intactos.

## Examples

- Guia minimal: preparar herramienta y despues ejecutar el perfil.
- Cache vacio: instalar/verificar los bytes oficiales y pasar 27 controles reales.
- Dependencia ausente: diagnostico explicito, ningun veredicto inventado.

## Do / Don't

- DO: inicializar una copia real y Git nuevo, ejecutar el comando extraido de guia.
- DON'T: heredar el binario de CI, simular el instalador o consultar red en tests.

## Tests

tests/test_bootstrap_cold_start.py verifica guias, orden, preparacion offline y
oraculos reales de sintaxis en la copia. La suite general post-apply existente
y los 1240 IDs se conservan. La inaplicabilidad de inicializar de nuevo una copia
ya inicializada se declara; los casos nuevos si se ejecutan en main.

## Constraints

No cambiar oraculos anteriores ni manifest/binarios aprobados de actionlint.
El fixture compartido esta sellado por bootstrap-filesystem-boundary.
PARAR y reportar si se necesita otro runtime, workflow o proteccion remota.
