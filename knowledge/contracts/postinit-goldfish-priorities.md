---
type: 'Task Contract'
title: 'Prioridades medidas para recuperar el margen del post-init de Windows'
description: 'Incorpora módulos lentos medidos después de ampliar la suite del PR 194.'
tags: ['ci', 'windows', 'performance']
task: postinit-goldfish-priorities
intent: 'Reducir la cola final del post-init de Windows con el mismo inventario.'
target: tools/ci/postinit-module-order.json
signature: 'JSON array of unique Python module names'
test_command: 'python -m unittest tests.test_postinit_goldfish_priorities'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_postinit_goldfish_priorities.py
tests_sha256: '9921625b49154ac245f92ee7c7b0f830c1e7556249ea20fdc25f9f9a1af7af9a'
oracle_files: ['tests/test_postinit_goldfish_priorities.py', 'tests/test_ci_module_order.py', 'tests/fixtures/pr194-original-module-order.json', 'tests/__init__.py']
touch_only: ['tools/ci/postinit-module-order.json', 'knowledge/postinit-module-order.md']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

Recuperar margen tras dos timeouts de `init-project` en Windows. En las
muestras completas, varios módulos de adopción, oráculos y trazabilidad
costosos quedan al final porque no están en el perfil de prioridades.

## Interface

Conservar el [lanzador y su perfil](postinit-module-order.md). Actualizar
`tools/ci/postinit-module-order.json` con los módulos tardíos que superan 30 s
en el perfil conservador. Este toma el máximo de la duración alojada de la
base y la duración del candidato local escalada por la razón entre las dos
duraciones de post-init. Registrar las fuentes, factores y resultado.

## Invariants

- Conservar el orden relativo de las 199 prioridades existentes. Insertar las
  nuevas cerca de trabajos de coste comparable. Los seis módulos tardíos de
  mayor coste deben quedar entre las primeras diecisiete prioridades. Los 17
  módulos añadidos deben quedar entre los primeros sesenta, por coste medido.
- Aplicar el orden solo al post-init de Windows. Conservar diez procesos en
  Windows, cuatro en Ubuntu, 600 s en `init-project`, el mismo discovery,
  los casos y SKIP aplicables, las dos pasadas generales y su cobertura inicial.
- Mantener completo el post-init de un proyecto sin `.git`. Conservar los
  fallos y medir el comando real antes de dar por recuperado el margen.

## Examples

- Un módulo de adopción medido en más de 100 s se ejecuta entre los primeros.
- Un módulo ajeno al perfil sigue apareciendo y se ejecuta una sola vez.

## Do / Don't

Usar el plan normal del runner para verificar orden e inventario. La
simulación sirve para seleccionar una propuesta e identificar su cola.

## Tests

Ejecutar el lanzador y el runner reales sobre una copia sin `.git` con
módulos representativos. Comprobar el perfil completo, el orden que recibe
Windows, el de Ubuntu y el inventario ejecutado en cada caso.

## Constraints

PARAR y reportar si se requiere variar el timeout, los workers, los workflows
o las protecciones. La aceptación del PR exige las dos pasadas por sistema y
los artefactos de cobertura, además del post-init Windows en menos de 600 s.
La meta de estabilidad del [perfil de Windows](../postinit-windows-runtime.md)
se comprueba con su protocolo de tres mediciones por debajo de 480 s.
