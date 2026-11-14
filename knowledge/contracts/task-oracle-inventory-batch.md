---
type: 'Task Contract'
title: 'Lectura agrupada del inventario de oraculos Git'
description: 'Reducir arranques Git por lectura de inventario conservando modos, bytes y frescura.'
tags: ['git', 'tasks', 'ci', 'performance']
task: task-oracle-inventory-batch
intent: 'Leer en lote el inventario aprobado y probado de tareas multiarchivo.'
target: scripts/task_git.py
signature: 'def _oracle_artifacts(root, revision, paths):'
test_command: 'python -m unittest tests.test_postinit_multi_oracle_headroom'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 4
tests: tests/test_postinit_multi_oracle_headroom.py
tests_sha256: '258e2ab315485eb2daef629911b118846de6c5d007b858314baf7ce140d74782'
oracle_files: ['tests/test_postinit_multi_oracle_headroom.py', 'tests/test_git_task_multi_oracle.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/trusted_ci.py']
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts', 'oracle_inventory']
forbids: ['network', 'llm']
---

## Intent

Reducir el trabajo repetido de Git observado en el
[post-init Windows](../postinit-windows-runtime.md) al verificar
[oraculos multiarchivo](git-task-multi-oracle.md).

## Interface

Conservar el punto de entrada del auditor para una revision. Para dos
revisiones, mantener una enumeracion exacta de modos y OID con ls-tree
por revision y leer en un solo cat-file --batch la union de blobs.
Se lee cada OID una vez dentro de la comprobacion.

## Invariants

- Leer modos y objetos sin reemplazos Git. Rechazar modos no regulares,
  rutas ausentes o ambiguas y entradas duplicadas. Conservar bytes
  binarios exactos. Una ruta ausente produce TASK_PATH y un blob
  ilegible o un fallo de Git produce TASK_GIT.
- No aceptar resultados parciales. No cambiar el lector de metadatos de
  otros flujos ni agregar una dependencia de versiones de Git nuevas.
- Aprobacion, revision probada, atributos y checkout mantienen sus
  comprobaciones. Se vuelve a consultar en cada etapa y despues de
  ejecutar los oraculos. El lote solo comparte bytes dentro de una etapa.
- La comprobacion de dos revisiones usa dos ls-tree y un cat-file --batch.
  No cuenta las consultas de atributos, grafo o estado que protegen otras
  garantias. Con una revision se conserva una enumeracion y una lectura.
- No cambian aprobaciones, recibos, perimetro, limites, inventarios previos
  ni cobertura. Conserva Ubuntu, Windows y las dos pasadas generales.

## Examples

- Contrato y auxiliares con dos SHA validos: una lectura agrupada observada
  con Trace2 tras enumerar los modos de las dos revisiones.
- Un blob de reemplazo o un modo 120000 con contenido identico no sustituye
  el archivo regular que se aprobo.

## Do / Don't

- DO reutilizar el lector de blobs por OID y la enumeracion exacta.
- DON'T reutilizar una comprobacion entre etapas o ejecutar los oraculos
  durante una auditoria historica.

## Tests

Git real, CLI de tareas, repositorios temporales y Trace2. Casos de aprobacion
con SHA distintos, enlaces con el mismo blob, reemplazos, entradas duplicadas,
rutas ausentes y un blob que desaparece durante el runner. Los oraculos
multiarchivo previos se conservan. Trace2 observa las tres etapas de cierre.
Un observador del subprocess registra los OID enviados al Git real para
comprobar su union exacta sin duplicados.

## Constraints

PARAR y reportar si requiere otro oraculo congelado, un cambio de runtime
confiable, un cambio de workflow o una proteccion remota.
