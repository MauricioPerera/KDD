---
type: 'Task Contract'
title: 'Edicion de Pages y nombres de importacion protegidos'
description: 'Permite editar la portada HTML existente con el modo regular original.'
tags: ['ci', 'security', 'pages', 'git']
task: trusted-pages-import-scope
intent: 'Distinguir una edicion de la portada de un cambio que pueda sombrear el modulo site.'
target: scripts/guard_pr_baseline.py
language: python
signature: 'def check(base_ref, candidate_ref, approved_ref, *, reviewed_changes=None):'
test_command: 'python -m unittest tests.test_trusted_pages_import_scope'
test_runner: python-unittest
test_scope: infrastructure
test_timeout: 180
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: tests/test_trusted_pages_import_scope.py
tests_sha256: '0df948afc5dbe99e891d43859310697632e54cd77741994764070281bdc9515a'
oracle_files: ['tests/test_trusted_pages_import_scope.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/guard_pr_baseline.py']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Corregir el rechazo de la portada HTML en el [PR #225](https://github.com/MauricioPerera/KDD/pull/225).

## Interface

El [guard](trusted-pr-gate.md) mantiene su API y CLI. Compara base y merge.

## Invariants

- Eximir solo `site/index.html` si ambos arboles Git originales la contienen
  como blob `100644`. Entradas ausentes, ambiguas o invalidas bloquean.
- Conservar los rechazos para otras rutas, ambos lados de renombres, modos
  distintos, cambios protegidos y deriva de contratos u oraculos.
- Usar objetos Git originales. El guard no lee el checkout del candidato
  ni ejecuta su codigo.

## Examples

- Editar el blob regular pasa.
- Reemplazarlo por un enlace falla.

## Do / Don't

- DO reutilizar la lectura de modos Git.

## Tests

Git real, merge distinto del head, modos, objetos de reemplazo y pruebas
mixtas con la portada editada.

## Constraints

- Revisar el cambio [protegido](trusted-ci-change-review.md). Integrarlo en
  la base y registrar el nuevo arbol con un baseline aprobado antes de
  generar otro evento de PR.
- PARAR y reportar si hay que cambiar oraculos, workflows o protecciones
  vigentes, o ampliar la excepcion.
