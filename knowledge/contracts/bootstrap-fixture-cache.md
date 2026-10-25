---
type: 'Task Contract'
title: 'Resolver el archivo offline del fixture desde la cache predeterminada'
description: 'Reproducir la preparacion local sin exports y preservar precedencia, hashes oficiales y fallo explicito.'
tags: ['bootstrap', 'fixture', 'cache', 'integration']
task: bootstrap-fixture-cache
intent: 'Hacer que el fixture use la misma cache predeterminada que el instalador revisado.'
target: tests/test_bootstrap_cold_start.py
language: python
signature: 'def reviewed_archive(self):'
test_command: 'python -m unittest tests/test_bootstrap_fixture_cache.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_bootstrap_fixture_cache.py
tests_sha256: '7b7395109bbeba887c0a70e3fd7fd396517c4b8cf424c155395d3e273632ffd2'
touch_only: ['tests/test_bootstrap_cold_start.py']
deps_allowed: ['stdlib', 'test_bootstrap_boundary']
forbids: ['network', 'llm']
---

## Intent

Cerrar la [seleccion del archivo](../review-p2-remediation.md) del
[arranque frio](../bootstrap-safety.md), conservando instalador y manifest.

## Interface

reviewed_archive conserva retorno (archivo copiado, pin), prioridad de variables
y PATH, SHA-256 oficial y errores de unittest. El fallback es la cache fijada.

## Invariants

- No descargar, instalar ni cambiar version durante la seleccion.
- Un origen seleccionado ausente o corrupto falla; no usar otro silenciosamente.
- Conservar las cuatro pruebas anteriores y todas sus aserciones.
- La adaptacion del oraculo necesita sello y baseline humano revisados.

## Examples

- Instalacion offline predeterminada sin exports: seleccionar el archivo instalado.
- Archivo explicito corrupto con cache buena: error, nunca fallback.
- Binario en PATH y archivo vecino valido: conservar esa seleccion.

## Do / Don't

- DO: usar el instalador y archivo oficial reales en temporales propios.
- DON'T: simular el instalador, depender de la cache del desarrollador o quitar asserts.

## Tests

tests/test_bootstrap_fixture_cache.py ejecuta el instalador y metodo reales en
procesos aislados. Cubre precedencia, ausencia, corrupcion y la guia que ejecuta
los 27 oraculos reales. Solo el caso de guia declara aplicabilidad de plantilla.

## Constraints

PARAR y reportar si se requiere otra version, cambiar checksums, workflow,
runtime o protecciones. Revisar el oraculo bajo
[quality-approval](../quality-approval.md) antes de adoptar su nuevo sello.
