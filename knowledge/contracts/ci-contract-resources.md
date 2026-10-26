---
type: 'Task Contract'
title: 'Exclusion explicita de comandos de contrato con suites anidadas'
description: 'Aislar los comandos pesados sin cambiar casos, limites, agrupacion ni perfiles por defecto de callers.'
tags: ['ci', 'performance', 'integration']
task: ci-contract-resources
intent: 'Ejecutar comandos exclusivos antes del pool normal conservando todos los resultados.'
target: scripts/validate_test_commands.py
language: python
signature: 'def run_all(contracts_dir, repo_root, timeout=600, deduplicate=False, workers=1, *, trusted_bundle=None, exclusive_commands=()):'
test_command: 'python -m unittest tests/test_contract_resource_scheduling.py'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: tests/test_contract_resource_scheduling.py
tests_sha256: '70f803ab174542a8db12961cda86be24b3c284c0107bac9abc5349e3c4c7b4eb'
touch_only: ['scripts/validate_test_commands.py', 'scripts/trusted_ci.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [politica y las mediciones](../windows-contract-resources.md),
conservando la [ejecucion confiable](ci-trusted-execution.md).

## Interface
exclusive_commands admite list/tuple de comandos exactos no vacios, distintos
y presentes en el inventario. Default (). El CLI del gate y trusted_ci commands
aceptan --exclusive-commands-json con default '[]'; rechazar JSON invalido.
El input reusable exclusive_contract_commands mantiene '[]' por defecto.

## Invariants
Conservar la politica enlazada, los perfiles y controles actuales. Ejecutar
todos los contratos aun si un exclusivo falla. Conservar deduplicacion exacta,
scopes, orden del reporte, shared_from, timeouts y limpieza de descendientes.
No modificar los oraculos previos ni el timeout de init-project. Dos pasadas
y matriz dual-OS permanecen; no agregar continue-on-error ni SKIP de cobertura.

## Examples
- init-project exclusivo: su suite anidada no comparte el lote con otros comandos.
- Dos contratos del mismo comando: un representante con dedup, dos sin dedup.
- Un comando exclusivo inexistente: FAIL antes de ejecutar el primer proceso.

## Do / Don't
- DO: validar toda la configuracion antes de ejecutar y registrar todos los resultados.
- DON'T: usar esperas estimadas para demostrar exclusion, omitir fallos o ampliar 600 s.

## Tests
El oraculo usa procesos reales con diarios por invocacion, barreras de inicio,
un comando que crea cuatro hijos, fallos, timeouts y CLI en un bundle real de Git.
Comprueba tambien compatibilidad del modo sin politica y el workflow literal.

## Constraints
PARAR y reportar si se necesita aprobar un runtime, cambiar un oraculo congelado
o alterar protecciones. La publicacion espera el baseline y el runtime revisados.
