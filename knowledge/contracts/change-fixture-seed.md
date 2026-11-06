---
type: 'Task Contract'
title: 'Preparacion unica del fixture de auditoria de cambios'
description: 'Preparar una base Git real por clase y entregar copias privadas a los casos existentes.'
tags: ['ci', 'performance', 'git', 'integration']
task: change-fixture-seed
intent: 'Evitar repetir la misma inicializacion sin compartir el estado mutable de los casos.'
target: tests/test_validate_change_contract.py
signature: 'class ChangeContractTests(unittest.TestCase):'
test_command: 'python -m unittest tests/test_change_fixture_seed.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_change_fixture_seed.py
tests_sha256: '641b1c8a11d267368f4acaec70841ec1e6953840bee32163c85b2c34ab179e47'
touch_only: ['tests/test_validate_change_contract.py']
deps_allowed: ['stdlib', 'git', 'validate_change_contract', 'change_contract_multilang']
forbids: ['network', 'llm']
---

## Intent
Reducir la preparacion del primer coste medido en el post-init Windows,
conforme a [la medicion](../postinit-module-order.md) y a la
[politica de oraculos](../quality-approval.md).

## Interface
La ejecucion normal de ChangeContractTests prepara un repositorio base real
una vez por clase y proceso. Cada setUp recibe su propio temporal y una copia
fisica completa de esa base: archivos, objetos, indice, configuracion y refs
independientes. No usar hardlinks, alternates, servicios ni cache entre runs.
Una invocacion manual de setUp fuera del ciclo de clase conserva su
inicializacion real, incluidos los dos commits del control de
[mantenimiento existente](existing-git-fixture-lifecycle.md).

## Invariants
- Conservar literalmente los 38 metodos test_ y sus aserciones. Los cuerpos
  del auditor, parsers y helpers de Git no cambian; tampoco los hallazgos.
- Tres casos normales preparan una base: un init y un commit inicial reales,
  no tres. Cada caso sigue creando y auditando sus propios cambios.
- Una modificacion de archivos, indice, objetos, refs o config de un caso no
  altera otro ni la base. Los archivos no versionados tampoco se comparten.
- Conservar maintenance.autoDetach=false y gc.autoDetach=false locales;
  no desactivar mantenimiento ni cambiar configuracion global o de sistema.
- Registrar limpieza antes de preparar/copiar. Un fallo real de Git al crear
  la base o una colision de archivos al copiar falla explicitamente, limpia
  los temporales propios y no publica ni reutiliza un estado incompleto.
- Otra invocacion de clase vuelve a preparar la base. Conservar limpieza
  estricta sin sleeps, reintentos, ignore_errors ni resultados cacheados.
- Mantener los 2104 IDs anteriores, Ubuntu/Windows y ambas suites generales.
  El ahorro aislado no acredita Windows <480 s ni las tres muestras remotas.

## Examples
- Tres copias modifican refs, indice y producto propios; las otras no cambian.
- Colision real en .git del destino: falla la copia y se limpia ese temporal.
- Config Git invalida durante setUpClass: falla, limpia y permite otra
  invocacion posterior con un entorno valido.

## Do / Don't
- DO medir con Git real y contar preparaciones, no sustituir Git por mocks.
- DON'T compartir la salida de una prueba, historial mutable u objetos.

## Tests
Tres integraciones nuevas cubren coste/aislamiento, limpieza/reinvocacion y
fallo/recuperacion de preparacion. Los seis controles existentes de ciclo de
vida y los 38 casos funcionales se ejecutan por separado sin duplicarlos.

## Constraints
El cambio de este fixture congelado requiere diff, sellos y baseline revisado
antes de adoptarlo. No cambiar runtime 74d357f, workflows, presupuesto Git 62,
timeout 600, protecciones ni fusionar el PR. El objetivo de 480 s sigue abierto.
PARAR y reportar si se necesita cambiar otro oraculo o frontera sin revision.
