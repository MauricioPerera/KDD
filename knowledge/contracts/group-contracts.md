---
type: 'Task Contract'
title: 'Validacion compuesta de contratos de grupo'
description: 'Verifica grupos anidados, contratos atomicos e integracion con una referencia Git explicita.'
tags: ['ccdd', 'groups', 'integration']
task: group-contracts
intent: 'Verificar grupos KDD completos sin perder aprobacion ni integridad.'
target: scripts/group_contracts.py
signature: 'def main():'
test_command: 'python -m unittest tests.test_group_contracts'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: 'tests/test_group_contracts.py'
tests_sha256: '9b8f4febabaa12f7572715889d2611aed02a10f3500fac09cea87765a8552e87'
touch_only: ['scripts/group_contracts.py']
deps_allowed: ['stdlib', 'scripts.validate_contracts', 'scripts.validate_test_commands']
forbids: ['network', 'llm']
---

## Intent
Implementar [contratos de grupo](../group-contracts.md) sin modificar los
contratos atomicos ni degradar la aprobacion de sus oraculos.

## Interface
CLI y formato definidos en el nodo enlazado; resultado JSON y exit 0, 1 o 2.

## Invariants
- Rechazar antes de ejecutar grafos invalidos o insumos no aprobados.
- Ejecutar cada hijo compartido una vez y ejecutar integracion solo tras hijos PASS.
- Verificar nuevamente insumos protegidos y el indice tras cada comando.
- No afirmar sandbox, identidad de revisor, Nivel 2 ni cobertura no verificados.

## Examples
- Grupo con hijos aprobados e integracion verde -> PASS con evidencia.
- Ciclo o archivo de pruebas alterado -> INVALID sin ejecutar candidatos.

## Do / Don't
- DO: reutilizar validacion y ejecucion atomicas existentes.
- DON'T: ejecutar shell, usar una referencia movil o omitir errores.

## Tests
Las integraciones reales en `tests/test_group_contracts.py` crean Git, contratos,
programas y procesos temporales. Sus fallos y limites se documentan en el nodo.

## Constraints
PARAR y reportar si es necesario cambiar runtime confiable, protecciones remotas
o prometer una aprobacion de dependencias que no esten enumeradas.
