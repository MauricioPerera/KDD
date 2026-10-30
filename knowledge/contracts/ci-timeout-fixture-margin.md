---
type: 'Task Contract'
title: 'Tolerancia al arranque lento del control de timeout'
description: 'Conservar la verificacion real de timeout y de ejecucion posterior ante arranque lento.'
tags: ['ci', 'integration', 'reliability']
task: ci-timeout-fixture-margin
intent: 'Evitar que una demora moderada del comando ligero haga fallar el oraculo de exclusion.'
target: tests/test_contract_resource_scheduling.py
language: python
signature: 'ContractResourceScheduling.test_exclusive_timeout_preserves_timeout_and_executes_the_rest'
test_command: 'python -m unittest tests/test_ci_resource_timeout_margin.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
tests: tests/test_ci_resource_timeout_margin.py
tests_sha256: 'a7970620af4810de68221337f0ad879585c99e8e4710eda47ed1ad00ccbda1d3'
touch_only: ['tests/test_contract_resource_scheduling.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Reforzar el control de [recursos de contrato](ci-contract-resources.md) ante el
fallo observado cuando el proceso ligero excedio 1,5 s en Windows.

## Interface
El test existente conserva su identificador, resultado timeout del comando
exclusivo, resultado exitoso del comando ligero y diario de fin. El margen debe
permitir dos segundos adicionales de demora real del proceso ligero; el proceso
de timeout permanece bloqueado mas tiempo que el limite probado.

## Invariants
No relajar el timeout de produccion, cambiar el runner, eliminar aserciones,
omitir resultados ni reducir los casos. La prueba sigue usando procesos reales;
Ubuntu/Windows y dos pasadas permanecen. El margen no garantiza estabilidad
ante una carga arbitraria y debe medirse en CI.

## Examples
- El exclusivo alcanza su timeout y el proceso ligero termina correctamente.
- El proceso ligero tarda dos segundos adicionales y sigue pasando el fixture.

## Do / Don't
- DO: probar la fixture existente mediante un proceso real demorado.
- DON'T: convertir un timeout del proceso ligero en un PASS.

## Tests
El oraculo nuevo ejecuta el metodo anterior completo con una demora adicional
controlada en su proceso ligero. Los resultados y aserciones anteriores se
conservan. Revisar el cambio del oraculo anterior y actualizar su sello.

## Constraints
PARAR y reportar si se necesita cambiar un oraculo existente sin revision y baseline
explicito, o modificar limites de produccion, runtime o protecciones sin autorizacion.
