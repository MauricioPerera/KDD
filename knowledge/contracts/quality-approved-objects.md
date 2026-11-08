---
type: 'Task Contract'
title: 'Objetos Git originales de la referencia de calidad'
description: 'Impedir que replacements sustituyan el baseline revisado de calidad.'
tags: ['quality', 'git', 'security', 'integration']
task: quality-approved-objects
intent: 'Conservar la identidad original de los objetos aprobados.'
target: scripts/verify_quality.py
signature: 'def approved_commit(root, reference):'
test_command: 'python -m unittest tests.test_quality_approved_objects'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_quality_approved_objects.py
tests_sha256: 'a3cca3d8a7d173b680efe65569ad7951c5fe62b78bd19eb154f3c7f7ceacb3eb'
oracle_files: ['tests/test_quality_approved_objects.py', 'tests/quality_review_fixture.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/verify_quality.py', 'scripts/quality_baseline.py']
deps_allowed: ['stdlib', 'verify_quality', 'baseline_review']
forbids: ['network', 'llm']
---

## Intent
Cumplir QBR-1 del [protocolo](../quality-board-audit-remediation.md)
durante la [aprobacion de calidad](../quality-approval.md).

## Interface
Conservar approve, approved_commit, build_baseline y ambas CLI. Leer objetos
originales en Git general y cat-file batch, incluidas las comprobaciones del
indice, politica, helper y perimetro anteriores y posteriores a cada check.

## Invariants
- Un SHA aprobado no selecciona contenido de un replacement de commit o blob.
- El namespace de replacements y su cambio durante un check no relajan el perimetro.
- No importar un helper no revisado aunque un replacement lo haga parecer aprobado.
- Conservar refs, indice y archivos; no retirar replacements del repositorio.
- Conservar las dos pasadas de los checks y los rechazos canonicos existentes.

## Examples
- Producto correcto y politica revisada -> PASS tras dos vueltas.
- Oraculos cambiados mas replacement del aprobado -> rechazo sin PASS global.
- Un check confirma un archivo ajeno y sustituye la base -> rechazo por perimetro.

## Do / Don't
- DO usar Git y procesos Python reales en repositorios independientes.
- DON'T simular resultados de Git ni ejecutar el helper sustituido.

## Tests
El oraculo distingue control correcto, defecto sin replacement, defecto con
replacement, lector batch, manifiesto, namespace, helper y efectos de un check.
Su fixture se congela con el oraculo; no modifica pruebas anteriores.

## Constraints
PARAR y reportar si falta aprobacion del commit de contratos y oraculos.
No modificar el runtime, workflows, protecciones ni otras pruebas congeladas.
