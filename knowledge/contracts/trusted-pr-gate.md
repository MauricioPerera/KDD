---
type: 'Task Contract'
title: 'Gate confiable para PR y referencia aprobada'
description: 'Compara el merge propuesto con una referencia aprobada usando el codigo de main, sin ejecutar el PR.'
tags: ['ccdd', 'security', 'ci']
task: trusted-pr-gate
intent: 'Impedir que un PR se autoapruebe al modificar su workflow o verificador de baseline.'
target: scripts/guard_pr_baseline.py
signature: 'def check(base_ref, candidate_ref, approved_ref):'
test_command: 'python -m unittest tests/test_guard_pr_baseline.py'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: 'tests/test_guard_pr_baseline.py'
tests_sha256: '4d54fe2ffd8dd338e7760901490007004ea1ffd0659345d8faa25b88a21aa77b'
touch_only: ['scripts/guard_pr_baseline.py', '.github/workflows/trusted-pr-gate.yml']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent

El [gate de referencia aprobada](./validate-baseline.md) corre en el workflow
del PR. Este gate adicional corre con `pull_request_target`, cuyo workflow y
script se toman de `main`. La propuesta se lee como datos de Git; no se hace
checkout ni se ejecuta codigo del PR en este gate.

## Interface

`check(base_ref, candidate_ref, approved_ref)` devuelve hallazgos. Compara
los contratos y oraculos de la propuesta con el commit aprobado y bloquea
cambios al workflow y a los validadores que forman la raiz de confianza.

## Invariants

- La referencia aprobada es un SHA completo configurado fuera del PR.
- Un contrato u oraculo agregado, eliminado o modificado sin aprobar falla.
- Un cambio al workflow o a los scripts protegidos falla incluso si el PR
  contiene el mismo SHA configurado como referencia aprobada.
- La politica de excepciones historicas de cierre y su validador tambien
  pertenecen a la raiz protegida; un PR no puede anadir una excepcion para
  autoaprobar un reporte incompleto.
- El clasificador de evidencia opcional tambien esta protegido: no se puede
  convertir un SKIP en PASS editando el helper dentro del mismo PR.
- El PR solo se lee mediante `git show`, `git diff` y `git ls-tree`.
- El gate no ejecuta scripts, pruebas ni comandos declarados por el PR.

## Examples

- Contratos, oraculos y gate intactos respecto del commit aprobado: PASS.
- Cambio al oraculo sin actualizar la referencia aprobada: FAIL.
- Cambio a `.github/workflows/trusted-pr-gate.yml`: FAIL.
- Cambio a `scripts/validate_baseline.py`: FAIL.

## Do / Don't

- DO: usar el merge propuesto y el codigo confiable de `main`.
- DO: exigir este check en la proteccion de `main` una vez publicado.
- DON'T: hacer checkout del head del PR en `pull_request_target`.
- DON'T: otorgar permisos de escritura al token de este workflow.

## Tests

`tests/test_guard_pr_baseline.py` crea repositorios temporales y comprueba
el caso sano y las modificaciones de contratos, oraculos y archivos del gate.

## Constraints

- Python stdlib y Git; sin dependencias Python externas.
- PARAR y reportar si la referencia aprobada no existe o el merge del PR no
  se puede leer.
