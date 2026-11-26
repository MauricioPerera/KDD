---
type: 'Task Contract'
title: 'Temporizacion del fixture HTTP de Pages'
description: 'Reproducir consultas y cancelaciones HTTP sin carreras de arranque.'
tags: ['ci', 'pages', 'testing']
task: pages-artifact-fixture-timing
intent: 'Separar el arranque de Node del vencimiento simulado en el fixture.'
target: tests/test_pages_artifact_delivery.py
language: python
signature: 'PagesArtifactDelivery.execute(self, responses, **options)'
test_command: 'python -m unittest tests.test_pages_artifact_fixture_timing'
test_runner: python-unittest
test_timeout: 90
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: tests/test_pages_artifact_fixture_timing.py
tests_sha256: '6471efff0ad0147feacf18ebf876a4f6a578100c37522fcc5519f2ac7f0ac460'
oracle_files: ['tests/test_pages_artifact_fixture_timing.py', 'tests/__init__.py']
touch_only: ['tests/test_pages_artifact_delivery.py']
deps_allowed: ['Python3.11', 'Node24', 'PyYAML']
forbids: ['llm']
---

## Intent

Estabilizar las pruebas del [paso de Pages](pages-inventory-ci.md).

## Interface

Ejecutar ese paso con Node y HTTP real por loopback.

## Invariants

- Consultas ordinarias conservan los 30 s del paso.
- Vencimiento simulado solo tras recibir la lista vacia o las cabeceras con
  el cuerpo aun pendiente. Usar una senal comun real para HTTP y espera.
- Preservar los 14 casos, sus aserciones y el limite externo del proceso.

## Examples

- Arranque lento y lista vacia: recibir un POST antes de cancelar.
- Cuerpo pendiente: cancelar sin aceptar el artefacto.

## Do / Don't

- DO sincronizar por eventos HTTP.
- DON'T acortar el plazo desde el arranque.

## Tests

Node real, servidor local e inicio de fetch demorado deliberadamente.

## Constraints

PARAR y reportar si hay que cambiar el workflow, limites de CI u oraculos ajenos.
