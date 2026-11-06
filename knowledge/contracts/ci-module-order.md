---
type: 'Task Contract'
title: 'Prioridad opt-in de modulos sin cambiar el inventario'
description: 'Despachar antes los modulos costosos conservando casos, procesos, fixtures y errores.'
tags: ['ci', 'performance', 'integration']
task: ci-module-order
intent: 'Reducir la cola ociosa medida sin omitir trabajo de la suite.'
target: scripts/run_test_suite.py
signature: 'def run_suite(start_dir, pattern="test_*.py", workers=1, *, module_order=None) -> dict:'
test_command: 'python -m unittest tests.test_ci_module_order'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_ci_module_order.py
tests_sha256: 'b7b326b45d6698305576fbcb8f70d18d024b7f4aa5a7fced79d4b5b6e98b0e8e'
touch_only: ['scripts/run_test_suite.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [medicion de orden](../postinit-module-order.md), manteniendo el
[runner](ci-suite-processes.md) y el [objetivo de margen](../postinit-windows-runtime.md).

## Interface
Agregar module_order opcional al API y --module-order PATH al CLI. El archivo
es un array JSON UTF-8 de nombres de origen de modulo, sin duplicados. Su orden
es una prioridad de despacho para workers>1, nunca una lista de seleccion.
Conservar por defecto el orden y la semantica existentes.

## Invariants
- Descubrir el inventario completo y crear exactamente los mismos jobs por
  origen. Priorizar coincidencias; conservar el orden relativo de los otros.
  Un nombre no descubierto se ignora y no se importa ni ejecuta por la lista.
- Cada modulo conserva su proceso, cwd, entorno, fixtures y todos sus IDs.
  Conservar el limite 1..8, deadlines, contencion y reconciliacion reales.
- Un perfil invalido, ilegible, con tipo distinto de array, nombres invalidos
  o duplicados falla con SUITE_ORDER antes de ejecutar casos. Una prioridad
  no vacia con workers1 falla; el modo serial ordinario no cambia.
- Propagar el argumento por el supervisor aislado al controlador. Reportar
  scheduling con profile_sha256 de los bytes leidos, modules en orden de
  despacho e ignored_priorities como cuenta. No acreditar el orden solo por
  ese campo: los tests deben observar los procesos y las barreras reales.
- No ocultar fallos, abortos, inventarios alterados, SKIP ni errores de import.
  Cada invocacion vuelve a ejecutar todos los casos; no reutilizar resultados.

## Examples
- Prioridades c,b con origenes a,b,c -> jobs c,b,a, mismos tres casos.
- Prioridad de un modulo ajeno -> no importarlo; ejecutar todos los descubiertos.
- JSON duplicado o malformado -> fallo y ningun testigo de ejecucion.

## Do / Don't
- DO ordenar jobs completos ya descubiertos, con procesos reales independientes.
- DON'T filtrar casos, dividir fixtures ni cambiar workers para aparentar ahorro.

## Tests
El oraculo compara CLI y API reales, barreras de dos procesos, origen ajeno,
errores, aborto, segunda invocacion y el lanzador post-init con/sin perfil.

## Constraints
PARAR y reportar si falta baseline humano antes de implementar. El runtime final requiere revision del
SHA y de sus seis hashes antes de registrarlo o publicarlo. No cambiar
protecciones, timeout 600, presupuesto Git 62 ni las dos suites del workflow.
