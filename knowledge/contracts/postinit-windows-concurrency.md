---
type: 'Task Contract'
title: 'Ensayo acotado de concurrencia post-init Windows'
description: 'Medir diez procesos del post-init Windows conservando ejecucion, aislamiento e inventario.'
tags: ['ci', 'windows', 'performance', 'integration']
task: postinit-windows-concurrency
intent: 'Medir el margen de una concurrencia mayor en el post-init Windows.'
target: scripts/init_post_apply_suite.py
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests.test_postinit_windows_concurrency'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_postinit_windows_concurrency.py
tests_sha256: '25d93c809bd351128e66b8b337969d8f4741a2da7593aaa58ae960a43c0f1e17'
touch_only: ['scripts/init_post_apply_suite.py', 'scripts/run_test_suite.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Medir una concurrencia mayor cuando el orden se aproxima al piso observado
de ocho procesos. Conservar el [protocolo](../postinit-proof-cost.md).

## Interface
El lanzador de una copia inicializada usa diez workers en Windows y cuatro
en Ubuntu. El runner acepta de uno a diez explicitamente. El default serial,
las dos pasadas generales y los workers de contratos conservan sus valores.

## Invariants
- Los modulos descubiertos se ejecutan en procesos independientes con cwd,
  entorno, fixtures, contencion, deadlines y reconciliacion intactos.
- Mantener los 2.210 IDs previos, los SKIP de aplicabilidad y el timeout 600.
  Los controles nuevos cuentan aparte. Las prioridades no seleccionan casos.
- El PR anterior midio 497,10 s en Windows. Su suite interna tardo 491,80 s
  frente al piso de 490,34 s con los costes observados. Cambiar el numero
  sigue siendo una hipotesis que debe medirse con el comando completo.
- La prueba local se interrumpio en el control de ocho por tiempo y limpieza.
  Medir en runners nativos tras la revision exacta de las referencias.
- Preservar cada resultado. Promover solo tras validar el PR y medir
  tres CI completos consecutivos del mismo SHA final en main bajo 480 s.

## Examples
- Diez modulos esperan una barrera real y terminan en diez procesos distintos.
- Once workers se rechazan antes del discovery.
- El lanzador conserva cuatro en Ubuntu y usa diez en Windows.

## Do / Don't
- DO cotejar los IDs de ambas pasadas y medir el comando completo.
- DON'T aumentar el timeout, seleccionar casos ni alterar protecciones.

## Tests
Barrera, rechazo del limite y lanzador con procesos reales. Los oraculos
anteriores conservan sus aserciones. El lanzador verifica el nuevo valor
de Windows y el runner prueba once como primer valor fuera del rango.

## Constraints
PARAR y reportar si falta el baseline, la revision exacta del cambio
protegido o la revision del runtime confiable. La fusion exige evidencia.
