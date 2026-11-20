---
type: 'Task Contract'
title: 'Preparacion de la semilla Git de adopcion'
description: 'Reducir la preparacion repetida con repositorios privados por caso.'
tags: ['ci', 'performance', 'git', 'adoption']
task: adoption-runtime-fixture-seed
intent: 'Conservar las pruebas reales de adopcion y reducir su preparacion repetida.'
target: tests/adoption_remediation_support.py
signature: 'def seed_repository(self):'
test_command: 'python -m unittest tests.test_adoption_runtime_fixture_seed'
test_runner: python-unittest
test_scope: infrastructure
budget:
  cyclomatic_max: 8
  nesting_max: 3
tests: tests/test_adoption_runtime_fixture_seed.py
tests_sha256: '353445cba49423090a13e64714c0dc1219b0794cdb3f065924a9813633c418f3'
oracle_files: ['tests/test_adoption_runtime_fixture_seed.py', 'tests/__init__.py']
touch_only: ['tests/adoption_remediation_support.py']
deps_allowed: ['stdlib', 'git']
forbids: ['network', 'llm']
---

## Intent
Acelerar los [oraculos de adopcion](adoption-adversarial.md) segun los [tiempos de CI](../ci-timing-diagnostics.md).

## Interface
`seed_repository()` devuelve ruta privada y dos SHA Git reales. Construir una
semilla completa por proceso. Entregar copias fisicas independientes.

## Invariants
- Tres llamadas en un interprete nuevo: un `git init` y hasta doce arranques Git.
- Aislar objetos, indice, refs, config y worktree. Evitar enlaces, alternates
  y estado compartido entre procesos. Cada caso puede escribir y confirmar.
- Conservar consumidores, oraculos, invocaciones y comprobantes independientes.
- Propagar fallos, limpiar recursos propios y publicar solo semillas completas.
- Conservar Ubuntu, Windows, perfil oficial, dos pasadas, cobertura en la
  primera y [plazo post-init](postinit-windows-common-deadline.md).

## Examples
- Tres casos reciben historia original y realizan cambios privados.
- El commit de un caso queda ausente en las otras copias.

## Do / Don't
- DO contar procesos con Git Trace2.
- DON'T copiar resultados ni comprobantes.

## Tests
Git real verifica costo, historia y aislamiento. Medir el ahorro de pared
con tres CI completos del mismo SHA.

## Constraints
PARAR y reportar si falta la [revision del oraculo](../quality-approval.md)
o se requiere cambiar el runtime del CI o el validador del consumidor.
