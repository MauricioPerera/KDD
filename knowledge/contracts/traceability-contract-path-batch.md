---
type: 'Task Contract'
title: 'Agrupar rutas del contrato en la proyeccion Git'
description: 'Reducir lecturas Git del oraculo y target sin cambiar seguridad ni resultados.'
tags: ['git', 'traceability', 'performance', 'integration']
task: traceability-contract-path-batch
intent: 'Agrupar comprobaciones de rutas conocidas en una operacion, preservando la proyeccion serial.'
target: scripts/traceability_git.py
language: python
signature: 'def build_trace(repo_root, ref, manifest_path, require_verified=False):'
test_command: 'python -m unittest tests/test_traceability_contract_batch.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_traceability_contract_batch.py
tests_sha256: 'f0e864a43e6aa7482634cd03b723035d1bcf545bf2fc253de63b03e3550e96a6'
touch_only: ['scripts/traceability_git.py']
deps_allowed: ['stdlib', 'traceability_model', 'task_git', 'task_model', 'task_evidence', 'validate_tasks', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent

Extender la [proyeccion Git](traceability-git.md) sin alterar sus garantias ni
el [protocolo de CI](../ci-runtime.md). Reducir procesos de comprobacion de
modos de rutas ya conocidas del oraculo y target de un contrato.

## Interface

Conservar `build_trace` y el reporte v1. Una proyeccion de contrato correcto
con oraculo y target regulares, distintos y sin relacion de prefijo comprueba
ambas rutas en una sola invocacion Git `ls-tree`; la ruta del contrato se lee
por separado antes de conocerlas. La lectura de blobs y sus sellos se conserva.
El caso de rutas identicas admite una unica comprobacion; rutas no regulares o
ambiguas pueden usar el camino serial para preservar errores.

## Invariants

Mantener valores, primer error, resultado y orden de validacion del lector
serial; no aceptar rutas ausentes, modos de enlace, arboles o submodulos como
archivos regulares. Los casos con relacion de prefijo no pueden inferirse de
una consulta agrupada que expanda un directorio. Los fallos de Git y blobs no
se transforman en exito. No consultar una lista vacia ni interpretar exit cero
como presencia de todas las rutas.

Conservar refs y cache conforme a [lecturas frescas](git-reader-ref-cache.md)
y [alcance del historial](../task-history-read-cost.md). No almacenar resultados
entre operaciones o repositorios, modificar checkout, ejecutar codigo del
producto, ni compartir resultados de pruebas. Conservar todos los oraculos,
Ubuntu/Windows y ambas pasadas independientes.

## Examples

- Oraculo y target distintos en el mismo SHA: una consulta de modos, dos blobs.
- Una ruta ausente antes de un enlace: el primer error coincide con el serial.
- `dir` y `dir/file`: rechazar como el serial, sin aceptar la expansion Git.
- Mover main o consultar otro repositorio no reutiliza evidencia anterior.

## Do / Don't

- DO: comparar Git real y errores exactos, con SHA-1 y SHA-256.
- DON'T: compartir verificaciones entre invocaciones o confiar solo en exit0.

## Tests

El [oraculo](../../tests/test_traceability_contract_batch.py) usa Git real,
Trace2 y una tarea realmente cerrada. Comprueba agrupacion, modos, ausencia,
prefijos, duplicados, caracteres invalidos, refs y aislamiento. Conservar los
oraculos historicos y las comprobaciones adversariales existentes.

## Constraints

Contratos y oraculos requieren baseline revisado antes de implementar. No
modificar runtime, workflows, protecciones ni otros modulos canonicos. Una
reduccion de procesos en un fixture no acredita ahorro total del CI.
PARAR y reportar si se necesita alterar un oraculo previo, el runtime o las
protecciones sin la revision correspondiente.
