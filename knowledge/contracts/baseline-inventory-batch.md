---
type: 'Task Contract'
title: 'Inventario de oraculos en baseline agrupado'
description: 'Conservar el inventario aprobado en las lecturas agrupadas de baseline.'
tags: ['git', 'baseline', 'security', 'integration']
task: baseline-inventory-batch
intent: 'Conservar la comparacion del inventario aprobado al agrupar lecturas Git.'
target: scripts/validate_baseline.py
signature: 'def validate_all_baselines(approved_ref, repo_root=".", contracts_dir="knowledge/contracts"):'
test_command: 'python -m unittest tests.test_baseline_inventory_batch'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tests/test_baseline_inventory_batch.py
oracle_files: [tests/test_baseline_inventory_batch.py, tests/__init__.py]
tests_sha256: '449e854ef00ded17afd2cfaceb2f9535ad7302e2a9c934a1165c8ecb7817591e'
touch_only: ['scripts/validate_baseline.py']
deps_allowed: ['stdlib', 'vendored-codex-security']
forbids: ['network', 'llm']
---

## Intent
Preservar [el inventario aprobado](oracle-inventory.md) en [lecturas agrupadas](baseline-git-batch.md).

## Interface
Las comprobaciones individual y `--all` usan el inventario del commit aprobado.

## Invariants
- Cada helper, fixture y oraculo aprobado se compara y una ausencia o modificacion falla.
- Un binario declarado en los atributos aprobados se compara byte a byte.
- Un symlink en el arbol aprobado no se acepta como archivo de inventario.
- Preservar la normalizacion de texto, seleccion explicita y lectura sin efectos.

## Examples
- Un helper modificado produce un finding tanto individual como en `--all`.
- Un archivo binario sin NUL con finales alterados falla en ambos modos.

## Do / Don't
- DO usar repositorios y objetos Git reales para los casos anteriores.
- DON'T interpretar un PASS parcial como proteccion del inventario completo.

## Tests
El oraculo ejecuta ambos modos en repositorios Git independientes y compara sus resultados.

## Constraints
PARAR y reportar si se requiere cambiar un oraculo previo, runtime o proteccion.
