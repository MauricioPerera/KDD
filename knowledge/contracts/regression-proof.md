---
type: 'Task Contract'
title: 'Prueba de regresion entre dos commits'
description: 'Comprobar el mismo oraculo en base y candidato con todos los intentos.'
tags: ['quality', 'git', 'verification']
task: regression-proof
intent: 'Atribuir el fallo esperado y la correccion al mismo oraculo sellado.'
target: scripts/prove_regression.py
language: python
signature: 'main(argv=None)'
test_command: 'python -m unittest tests.test_regression_proof'
test_runner: python-unittest
test_timeout: 120
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: tests/test_regression_proof.py
tests_sha256: '245b62787dc3ff6d1511cfd8e1d88279ea90812ec4cb6c98a275e07cb7fcc1d9'
oracle_files: ['tests/test_regression_proof.py', 'tests/__init__.py']
touch_only: ['scripts/prove_regression.py']
deps_allowed: ['stdlib', 'git', 'oracle_execution', 'unittest_oracle_runner', 'process_tree']
forbids: ['llm']
---

## Intent

Complementar la [evidencia de oraculos](oracle-execution.md).

## Interface

`python scripts/prove_regression.py --repo-root DIR --base SHA --candidate SHA
--contract SLUG --expect-failure ID`. Repetir ID para otros fallos esperados.
JSON v1 con commits, SHA256 de oraculos y cuatro intentos numerados.
Salida 0 proven, 1 inconclusive, 2 invalid.

## Invariants

- Base ancestro estricto. Usar objetos Git originales y archivos regulares.
  Contrato, sello e inventario iguales. Rechazar deriva antes de ejecutar.
- Verificar cada copia contra rutas, modos y blobs del arbol completo.
- Dos pasadas por lado en temporales nuevos. Solo unittest declarado con
  metodos simples del inventario, sin wrappers, cierres, defaults ni subtests.
  Exigir los mismos IDs y huellas. Ambas bases fallan por asercion en
  exactamente los IDs esperados, con tipo AssertionError. Ambos candidatos pasan.
- Cada intento identifica lado, numero, estado, casos y fallos.
  Errores, saltos, inventario incompleto o timeout impiden probar.

## Examples

- Misma prueba roja dos veces y verde dos veces prueba la regresion.
- Verde posterior a un fallo del candidato queda inconcluso.

## Do / Don't

- DO aislar el proceso y respetar el plazo del contrato.
- DON'T inferir fallos de stdout. Registrar callbacks de unittest en el
  runner hijo sin escribir en el checkout original.

## Tests

CLI, Git y unittest reales con copias, aserciones y fallos de entorno.

## Constraints

Herramienta local para commits confiables. PARAR y reportar si requiere
cambiar runners, aprobaciones o CI.
