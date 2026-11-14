---
type: 'Task Contract'
title: 'Prioridades de los modulos rezagados en post-init'
description: 'Adelantar los nueve modulos observados al final de la cola Windows.'
tags: ['bootstrap', 'ci', 'windows', 'performance']
task: postinit-multi-oracle-priority
intent: 'Insertar en el perfil Windows los nueve modulos faltantes con sus costes medidos.'
target: tools/ci/postinit-module-order.json
signature: 'ordered JSON array of module names'
test_command: 'python -m unittest tests.test_postinit_multi_oracle_headroom'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 4
  params_max: 4
tests: tests/test_postinit_multi_oracle_headroom.py
tests_sha256: '258e2ab315485eb2daef629911b118846de6c5d007b858314baf7ce140d74782'
oracle_files: ['tests/test_postinit_multi_oracle_headroom.py', 'tests/test_git_task_multi_oracle.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py']
touch_only: ['tools/ci/postinit-module-order.json']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

Adelantar un modulo observado en la cola final de Windows. En el tercer
intento del run 43225471386, su duracion fue 85,67 segundos y su posicion
206 de 208 con diez workers. Los otros ocho modulos sin prioridad tambien
ocupaban las ultimas nueve posiciones.

## Interface

Insertar los nueve modulos de la muestra que faltaban en el perfil Windows
antes de la primera entrada de menor duracion, del mas lento al mas rapido.
test_git_task_multi_oracle queda en segunda posicion. El perfil solo ordena
la ejecucion. La suite inicializada ejecuta todos sus casos con el lanzador nativo.

## Invariants

- Conservar el orden relativo de todos los modulos ya priorizados. Los
  modulos que no aparecen en el perfil se descubren y ejecutan igual.
- Conservar diez workers del post-init en Windows y cuatro en Ubuntu. Las
  suites generales de Ubuntu y Windows siguen corriendo dos veces con sus
  perfiles actuales. Conservar los 600 segundos operativos.
- Los dos timeouts de main se conservan como muestras censuradas y el
  perfil exitoso no se usa como evidencia causal de esos timeouts.
- Comparar inventario y tiempos completos. El cierre exige tres CI
  consecutivos completos del mismo SHA de main, cada uno con post-init
  Windows estrictamente inferior a 480 segundos. Conservar cada intento.

## Examples

- El modulo multiarchivo y las otras ocho incorporaciones aparecen una vez
  en sus posiciones medidas. Los modulos previos conservan su orden.
- Ubuntu ejecuta los mismos casos con su orden y sus cuatro workers.

## Do / Don't

- DO verificar el comando completo con el perfil oficial.
- DON'T convertir una simulacion de cola en una medicion real.

## Tests

Lectura del perfil real, Git y lanzador nativo sobre una suite temporal.
La prueba verifica que tambien se ejecuten modulos sin prioridad.

## Constraints

PARAR y reportar si requiere cambiar runtime, workflow, cobertura o
protecciones. Mantener el historial de commits y revisiones aprobadas.
