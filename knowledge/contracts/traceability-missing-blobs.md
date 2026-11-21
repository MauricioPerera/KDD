---
type: 'Task Contract'
title: 'Preservar el primer error con blobs ausentes en la lectura agrupada'
description: 'Amplia el oraculo de trazabilidad cuando el arbol conserva las dos entradas regulares.'
tags: ['git', 'traceability', 'oracle', 'integration']
task: traceability-missing-blobs
intent: 'Demostrar equivalencia con el lector serial ante la ausencia de los objetos del oraculo o del target.'
target: scripts/traceability_git.py
language: python
signature: 'def build_trace(repo_root, ref, manifest_path, require_verified=False):'
test_command: 'python -m unittest tests.test_traceability_missing_blobs'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_traceability_missing_blobs.py
tests_sha256: '440aad7249f40e1b60c58bf66d6c1161e35e4663bf09769a507d270433aafadd'
oracle_files: ['tests/test_traceability_missing_blobs.py', 'tests/test_traceability_contract_batch.py', 'tests/test_traceability_model.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py']
touch_only: ['scripts/traceability_git.py']
deps_allowed: ['stdlib', 'traceability_model', 'task_git', 'task_model', 'task_evidence', 'validate_tasks', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent

Completar la cobertura del [oraculo de rutas agrupadas](traceability-contract-path-batch.md)
para un commit cuyo arbol conserva dos entradas regulares, pero cuyos objetos
pueden faltar. Mantener intactos el contrato, el oraculo y el sello historicos.

## Interface

Conservar `build_trace`, el reporte v1 y el orden observable de los errores.
Las dos rutas regulares son distintas, sin relacion de prefijo, y pertenecen al
mismo commit del fixture. La lectura agrupada usa una consulta de modos
`ls-tree` para el par y conserva el error exacto de la lectura serial.

## Invariants

- La ausencia de un objeto con entrada regular en el arbol produce `TASK_GIT`.
- La lectura serial y la agrupada identifican la misma ruta en el primer error.
  Si faltan ambos objetos, tiene precedencia el oraculo.
- Con ambos objetos presentes coinciden el resultado y el sello del oraculo.
- Las dos entradas del arbol conservan sus OID y modos despues de retirar
  objetos. Cada caso usa un repositorio temporal propio y lecturas independientes.

## Examples

- Falta el objeto de `tests/test_value.py`: ambas lecturas identifican esa ruta.
- Falta el objeto de `src/value.py`: ambas lecturas identifican esa ruta.
- Faltan ambos objetos: ambas lecturas identifican primero `tests/test_value.py`.

## Do / Don't

- DO: usar Git real, comparar los errores exactos y capturar Trace2 solo en la
  lectura agrupada.
- DON'T: retirar entradas del arbol para simular un objeto ausente o modificar el
  repositorio que contiene el candidato.

## Tests

El [oraculo complementario](../../tests/test_traceability_missing_blobs.py)
ejecuta los tres escenarios con SHA-1 y SHA-256. Antes de retirar los objetos
comprueba una lectura de control con el arbol completo. Comprueba que la lectura
agrupada conserva una consulta de modos para el par cuando falla la de blobs.

## Constraints

El candidato de baseline incorpora unicamente este contrato y su oraculo.
Conservar el runtime, los workflows, las protecciones y las dos pasadas en
Ubuntu y Windows. La medicion del fixture cubre el recuento de consultas del
par; el tiempo total de CI queda fuera de su alcance.

PARAR y reportar si la ampliacion exige cambiar el oraculo sellado anterior,
la implementacion de trazabilidad, el runtime o las protecciones.
