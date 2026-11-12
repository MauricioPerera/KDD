---
type: 'Task Contract'
title: 'Aislar las herramientas de la accion compuesta'
description: 'Conservar el perimetro del consumidor al ejecutar la calidad con el KDD fijado.'
tags: ['ci', 'adoption', 'quality']
task: composite-quality-checkout
intent: 'Ejecutar el verificador fijado fuera del arbol auditado del consumidor.'
target: .github/actions/validate-contracts/action.yml
signature: 'Composite action validate-contracts with kdd-ref and quality-approved-ref inputs'
test_command: 'python -m unittest tests.test_composite_quality_checkout'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: tests/test_composite_quality_checkout.py
tests_sha256: '27aa282523521710bd3f74030e71351c2f4956f7f1b3bcf9d55c1eb0de0329a4'
oracle_files: ['tests/test_composite_quality_checkout.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['.github/actions/validate-contracts/action.yml', 'README.md']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Permitir que la accion compuesta ejecute la [calidad](../quality-approval.md)
del consumidor sin que su propio checkout altere el perimetro.

## Interface

Se conservan los inputs de la accion compuesta, la exigencia de SHA completo
en `kdd-ref`, la opcion `run-test-commands`, la resolucion repo-relativa de
las rutas y el checkout previo del consumidor. El paso `Check out KDD tooling repo`
comunica la ruta privada a los validadores por su salida `root`, leida
mediante el entorno `KDD_TOOLING_ROOT` de cada paso consumidor. El paso
`Approve project quality (when configured)` ejecuta el verificador contra el
repositorio del consumidor y su SHA aprobado.

## Invariants

- El checkout de `MauricioPerera/KDD` se fija al commit solicitado y vive en
  un directorio privado de `RUNNER_TEMP`, fisicamente fuera del arbol Git
  del consumidor. Un temporal que cae dentro de ese arbol se rechaza antes
  de crear archivos, incluidos aliases al mismo directorio. Un SHA erroneo
  no permite ejecutar validadores ni el resumen que necesita ese checkout.
- Los validadores, comandos y resumen resuelven sus herramientas en ese
  checkout fijado. Las rutas de entrada y la auditoria de calidad siguen
  referidas al consumidor. Un fallo de preparacion bloquea la ejecucion.
- El checkout no aporta archivos al inventario de cambios del consumidor.
  Un directorio `_kdd` del consumidor se conserva. La accion no introduce
  reglas de exclusiones ni modifica el indice del consumidor.
- Un consumidor con politica y el helper aprobado `scripts/process_tree.py`
  ejecuta las dos rondas existentes. Archivos ajenos al perimetro y falta de
  referencia o helper aprobado siguen fallando. Sin politica ni aprobacion,
  la comprobacion opcional conserva SKIP.

## Examples

- En un consumidor limpio sin `_kdd`, el paso de calidad ejecuta dos rondas.
- Si el consumidor tiene `_kdd/documento.txt` versionado, conserva sus bytes.
- Una ruta nueva ajena al perimetro falla aun con las herramientas aisladas.

## Do / Don't

- DO usar el commit fijado de KDD y un checkout privado del runner.
- DON'T ignorar archivos del consumidor para compensar escrituras del tooling.

## Tests

El oraculo ejecuta los cuerpos reales Bash de preparacion y calidad contra
repositorios Git descartables. En Windows, el fixture resuelve Bash del
mismo Git for Windows desde el lanzador o el binario directo de CI.
La URL publica de KDD se redirige a un remoto
local para ejercitar fetch real sin depender de GitHub. Conserva dos rondas,
rechazo del perimetro y un control del temporal interno.

## Constraints

El runner de Actions, Git y Python siguen siendo prerrequisitos. La accion
solo lee el repositorio de herramientas. La revision y el registro de cambios
protegidos se hacen antes de publicar.

PARAR y reportar si se requiere modificar el perimetro aprobado o la configuracion del consumidor.
