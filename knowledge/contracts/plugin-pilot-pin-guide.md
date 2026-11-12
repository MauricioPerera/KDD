---
type: 'Task Contract'
title: 'Compatibilidad del pin de la release 1.2.0'
description: 'Distingue la actualizacion historica del complemento y los requisitos del piloto ODD y EGM.'
tags: ['adoption', 'plugin', 'documentation']
task: plugin-pilot-pin-guide
intent: 'Permitir que el operador elija el lanzador y el pin segun las capacidades que necesita.'
target: plugins/kdd-codex/README.md
signature: '## Review in an adopted project'
test_command: 'python -m unittest tests/test_plugin_pilot_pin_guide.py'
test_runner: python-unittest
test_scope: infrastructure
budget:
  cyclomatic_max: 10
  nesting_max: 3
tests: tests/test_plugin_pilot_pin_guide.py
tests_sha256: '96205b2de0dc62ace9b1c98b70be74812f56d1c7e3914014e3fdb002347fab05'
oracle_files: ['tests/test_plugin_pilot_pin_guide.py', 'tests/__init__.py']
touch_only: ['plugins/kdd-codex/README.md', 'plugins/kdd-codex/skills/kdd-workflow/SKILL.md', 'tools/kdd-adoption/README.md']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent

Mantener verificable la [release y su piloto](../piloto-kdd-complemento.md)
al explicar las capacidades nuevas de [revision](plugin-odd-egm-review.md)
y [comprobantes](adoption-bound-method-identity.md).

## Interface

La guia de la release conserva el pin completo
`144168d168410c28315f07d53e87638a4a10b81c` y su enlace versionado.
El README, la skill y la guia del consumidor delimitan los requisitos
del piloto en el lugar donde se presenta su comando de revision.

## Invariants

- La release 1.2.0 acredita `verified_kdd_sha` y dos conteos en la
  adopcion aprobada. Su instalacion historica carece del subcomando
  `review` y de comprobantes de IDs por contrato.
- El piloto requiere el lanzador generado compatible y un pin completo
  revisado que provea el revisor y los comprobantes de identidad del
  metodo enlazado. Documentar la revision de los cambios en archivos
  administrados y la referencia de adopcion antes del uso en CI.
- Conservar la receta de actualizacion historica. La documentacion del
  piloto no presenta el tag ni el ZIP de 1.2.0 como instaladores del
  lanzador del piloto.

## Examples

- Proyecto fijado a 1.2.0 → comparar SHA y conteos del perfil historico.
- Lanzador compatible y pin aprobado del piloto → ejecutar `review` y
  comparar la evidencia por contrato.

## Do / Don't

- DO distinguir el paquete, el lanzador del consumidor y su pin.
- DON'T atribuir las capacidades del piloto al pin de la release.

## Tests

Comprobar las guias versionadas desde la plantilla y la copia
inicializada, aun sin historial Git. Como evidencia de revision, ejecutar
el lanzador y gate extraidos del objeto Git exacto de la release.

## Constraints

PARAR y reportar si se requiere cambiar un tag, un paquete publicado
o la referencia aprobada de un consumidor real.
