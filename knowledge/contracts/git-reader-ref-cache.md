---
type: 'Task Contract'
title: 'Referencias moviles frescas en los lectores cacheados'
description: 'Cachear solo OIDs nativos inmutables al leer commits, blobs, inventarios y modos.'
tags: ['git', 'cache', 'integration']
task: git-reader-ref-cache
intent: 'Evitar valores anteriores al mover una rama hexadecimal durante una operacion.'
target: scripts/task_git.py
language: python
signature: 'def commit_sha(root, ref):'
test_command: 'python -m unittest tests/test_git_reader_ref_cache.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 160
  params_max: 5
tests: tests/test_git_reader_ref_cache.py
tests_sha256: '8e43deee1313367deb79caeeddd723c8a23e1bdaff505314ae43360975d85b1d'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [protocolo](../audit-quality-cache-onboarding.md), preservando
la [medicion de historial](../task-history-read-cost.md).

## Interface
Conservar commit_sha, blob/blobs, paths, _committed_paths y object_cache.
Mismas excepciones y resultados. Sin cache persistente o nuevas dependencias.

## Invariants
OID completo corresponde al formato nativo del repositorio; otros nombres
son referencias moviles y deben resolverse de nuevo. Claves por repositorio y
OID resuelto, sin reutilizar fallos ni una comprobacion de modo bajo un alias.
Mantener controles de ancestros, modos regulares, paths, limites Git y limpieza
al salir de la operacion, tambien con excepcion. No alterar Git para consultar.

## Examples
- Rama 64 hex en SHA-1 cambia A por B: los cuatro lectores ven B.
- Cambia de archivo regular a 120000: se rechaza aunque antes se haya leido.
- OID nativo repetido conserva ahorro; otra operacion vuelve a consultar.

## Do / Don't
- DO: Git/Trace2 reales, SHA-1/SHA-256 y refs movidas con update-ref.
- DON'T: decidir inmutabilidad por valid_sha solamente o reducir la auditoria.

## Tests
tests/test_git_reader_ref_cache.py prueba frescura, OIDs, modos, errores,
contextos, repositorios y presupuestos con Git real. Ningun SKIP ni mock de Git.

## Constraints
PARAR y reportar si se necesita modificar un oraculo previo, el runtime
aprobado, un workflow o una proteccion remota.
No modificar otros modulos de produccion, runtime, workflows o protecciones.
Conservar todos los oraculos anteriores y sus presupuestos; baseline humano
antes de implementar.
