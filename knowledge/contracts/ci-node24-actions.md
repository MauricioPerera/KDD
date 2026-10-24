---
type: 'Task Contract'
title: 'Actions oficiales con runtime Node24'
description: 'Actualizar pins oficiales sin modificar las garantias del CI.'
tags: ['quality', 'maintenance', 'verification']
task: ci-node24-actions
intent: 'Actualizar pins oficiales sin modificar las garantias del CI.'
target: .github/workflows/validate.yml
language: yaml
signature: 'validate_contracts(validate, board)'
test_command: 'python -m unittest tests/test_ci_action_runtime.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_ci_action_runtime.py
tests_sha256: '8e6e9af9bc3175e9bcb61759359c6e58a28dedaea0fc858c005c8003ae51039a'
touch_only: ['.github/workflows/validate.yml', '.github/workflows/trusted-pr-gate.yml', '.github/workflows/deploy-pages.yml', '.github/actions/validate-contracts/action.yml']
deps_allowed: ['node', 'fastwebmcp', 'zod']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Pins oficiales revisados de checkout/setup-python/setup-node y las tres Actions de Pages; runtime Node24, incluido upload-artifact anidado y build de Pages. Matriz, comandos, permisos y controles conservados. Registrar fuente y manifests oficiales en informe.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- Actions revisadas runs.using node24 -> workflow conserva suites identicas 2x.
- Tag flotante, SHA anterior, menos gates o suites distintas -> fallo.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tests/test_ci_action_runtime.py. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
