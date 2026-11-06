---
type: 'Task Contract'
title: 'Semantica de objetos Git en lecturas agrupadas'
description: 'Conservar lecturas Git actuales y rechazar objetos commit malformados.'
tags: ['git', 'bootstrap', 'integrity', 'integration']
task: postinit-git-read-semantics
intent: 'Evitar que optimizaciones acepten objetos invalidos o ignoren reemplazos Git.'
target: scripts/task_git.py
signature: 'def object_cache():'
test_command: 'python -m unittest tests.test_postinit_git_read_semantics'
test_runner: python-unittest
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 160
  params_max: 5
tests: tests/test_postinit_git_read_semantics.py
tests_sha256: 'a472eb28a788b5966690f70963d1406c67d474d62358f549e0db685fcbf525b4'
touch_only: ['scripts/task_git.py', 'scripts/traceability_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Conservar la semantica de Git al agrupar lecturas en las auditorias post-init.

## Interface
Una lectura de un camino todavia no consultado debe observar el reemplazo Git
realizado despues de otra lectura. Las identidades del perimetro deben rechazar
commits ausentes o malformados, incluso cuando Git informe que su tipo es commit.

## Invariants
- Los lotes son acotados y no convierten un objeto corrupto en commit valido.
- Un fallo no contamina una comprobacion valida posterior en la misma operacion.
- El control del perimetro conserva sus validaciones de historial y alcance.
- Se conservan Ubuntu, Windows y las dos pasadas completas de la suite.

## Examples
- Un reemplazo entre dos lecturas de caminos distintos devuelve el contenido actual.
- Un objeto creado con `git hash-object --literally` no acredita un commit valido.

## Do / Don't
- DO utilizar repositorios y objetos Git reales.
- DON'T confiar solo en el tipo reportado por `git cat-file --batch-check`.

## Tests
El oraculo comprueba reemplazos, commits malformados y ausentes, y recuperacion.

## Constraints
PARAR y reportar si se necesita cambiar runtime, timeout, protecciones o un
oraculo sin la revision exigida por `knowledge/quality-approval.md`.
