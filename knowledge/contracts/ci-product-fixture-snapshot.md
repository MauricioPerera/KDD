---
type: 'Task Contract'
title: 'Preparacion acotada del producto de routing con clones independientes'
description: 'Preparar una fuente una vez por clase sin compartir estados mutables ni relajar limites.'
tags: ['ci', 'fixtures', 'integration']
task: ci-product-fixture-snapshot
intent: 'Eliminar staging y bootstrap repetidos del fixture que excedio 60 s en Windows.'
target: tests/test_approval_routing.py
language: python
signature: 'def fresh_product(self, area):'
test_command: 'python -m unittest tests/test_ci_product_fixture_snapshot.py'
budget:
  cyclomatic_max: 18
  nesting_max: 4
tests: tests/test_ci_product_fixture_snapshot.py
tests_sha256: 'a9be305675f0b98ed2339dd80fdbb3cdda05d0053a5d3c9747199df93de04a39'
touch_only: ['tests/test_approval_routing.py']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---
## Intent
Aplicar el [protocolo de instantaneas](../ci-product-fixture-snapshot.md) al
fixture de [routing](approval-routing.md), sin cambiar produccion ni runtime.
## Interface
Conservar fresh_product(area) y su tupla. Fuente completa: bootstrap real;
inicializada: no reinicializar; parcial: ValueError antes de preparar Git.
Una identidad de fuentes por nombres/ruta/bytes prepara una vez por clase.
Cada llamada devuelve un clon nuevo sin hardlinks ni alternates, con mantenimiento
sin detach y EOL sin conversion configurados antes del checkout. Un cambio invalida la instantanea.
## Invariants
Conservar nueve metodos, aserciones y limites anteriores. No usar cache global,
resultados previos de calidad ni copias mutables compartidas. Los checks reales
del producto siguen corriendo dos veces. No nuevos SKIP en KDD ni ampliar limites.
Conservar Ubuntu/Windows, dos suites completas y perfiles de workers aprobados.
## Examples
- Tres productos de una fuente: una preparacion y tres clones independientes.
- Cambiar bytes sin variar nombre/mtime/tamano: nueva preparacion y nuevos refs.
- Una fuente parcial falla; una inicializada sin .git sigue verificandose.
## Do / Don't
- DO medir procesos reales y verificar aislamiento de archivos, refs y objetos.
- DON'T reemplazar controles, aumentar timeouts o contar el CI fallido como verde.
## Tests
El oraculo ejecuta Git, calidad y mutaciones reales en fuentes minimas de control.
Un cambio real durante git init debe impedir publicar la instantanea o clonar.
La integracion existente sigue usando el bootstrap completo. Una copia realmente
inicializada sin .git ni test_init_project ejecuta los nuevos controles y verifica
solo los tres SKIP existentes de plantilla, sin errores de discovery.
## Constraints
PARAR y reportar si necesita otro baseline/runtime o modificar protecciones.
Adoptar el helper solo despues de revisar el SHA de este oraculo y sus sellos.
