---
type: 'Task Contract'
title: 'Barrera de terminacion de procesos propios en Windows'
description: 'Acreditar el cierre mediante handles senalados y contador cero, conservando la gracia y la semantica de los callers.'
tags: ['processes', 'windows', 'integration']
task: process-exit-barrier
intent: 'Completar la espera de miembros del Job antes de devolver resultados y liberar temporales.'
target: scripts/process_tree.py
language: python
signature: 'def run(argv, *, cwd, timeout, **kwargs):'
test_command: 'python -m unittest tests/test_process_exit_barrier.py'
budget:
  cyclomatic_max: 18
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_process_exit_barrier.py
tests_sha256: '8a10b404cf8da668d79d7248596b80479ec588aa4f4b628d400a7f35e69918e4'
touch_only: ['scripts/process_tree.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [barrera y su evidencia](../process-exit-barrier.md), conservando
la [contencion existente](process-tree-timeout.md) y la
[ejecucion confiable](ci-trusted-execution.md).

## Interface
Conservar run(argv, *, cwd, timeout, **kwargs), CompletedProcess y sus
excepciones. La mejora es interna al backend Windows y a su limpieza.

## Invariants
Cumplir el protocolo enlazado: handles propios retenidos y senalados,
contador cero, errores explicitos y liberacion en todos los caminos.
La gracia compartida sigue siendo cinco segundos, sin ampliacion del
timeout de ejecucion. Mantener POSIX, Unicode, cwd, env y vecinos sanos.

## Examples
- Tres generaciones listas: al retornar, sus handles observados ya estan senalados.
- Un vecino ajeno completa su trabajo mientras la invocacion propia se cancela.
- Un error de backend se propaga; no acredita una cancelacion normal.

## Do / Don't
- DO: readiness real y comprobacion nativa independiente del contador.
- DON'T: ocultar WinError32 mediante SKIP, retry de la suite o borrado global de procesos.

## Tests
Oraculo nuevo con arboles reales, exito con descendientes en segundo plano,
timeout, vecinos independientes, recursos y errores. Conserva los archivos
y aserciones anteriores. Cada plataforma ejecuta sus controles de backend.

## Constraints
PARAR y reportar si se necesita adoptar un baseline no revisado o registrar un
runtime nuevo. Su SHA y seis hashes finales requieren aprobacion explicita
posterior. No tocar workflows, oraculos previos ni protecciones.
