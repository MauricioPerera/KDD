---
type: 'Task Contract'
title: 'Reducir complejidad del verificador de calidad'
description: 'Cumplir los presupuestos vigentes conservando las fronteras de aprobacion.'
tags: ['quality', 'budget', 'git', 'integration']
task: verify-quality-complexity
intent: 'Eliminar excesos de verify_quality sin modificar los limites ni la aprobacion.'
target: scripts/verify_quality.py
signature: 'def approve(root, policy_path, reference):'
test_command: 'python -m unittest tests.test_verify_quality_complexity'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_verify_quality_complexity.py
tests_sha256: '6c4ac5412f66edca0dd51e5fecadf7957b19aa9e8b900049bf1b7359e9681f77'
touch_only: ['scripts/verify_quality.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Eliminar los doce hallazgos del diagnostico actual asociados a
[calidad](verify-quality.md), [identidad](quality-ref-canonical.md),
[procesos](quality-process-lifecycle.md) y [evidencia](quality-task-evidence.md).

## Interface
Conservar la CLI, las firmas y el comportamiento de `approve`, `validate_policy`
y las APIs usadas por `quality_baseline.py`. `integrity` es un helper interno
sin llamadores externos en este repositorio: puede retirar su argumento
`policy_path`, que no usa; los demas parametros y comprobaciones se conservan.

## Invariants
- Cumplir los presupuestos mas estrictos declarados para el modulo: complejidad
  ciclomatica 12, anidamiento 4, 150 lineas y cinco parametros; aplicar a todos
  los helpers nuevos sin alterar el medidor ni subir limites existentes.
- Conservar referencia Git inmutable, politica aprobada, proteccion del indice y
  del checkout, perimetro, evidencias de tareas, batching y helper de procesos
  obtenido de la referencia aprobada; comprobar integridad tras cada check,
  incluso si falla o agota su tiempo.
- Conservar el orden, las dos pasadas, errores, limites y cobertura existentes;
  no cambiar oraculos anteriores, runtime, workflows ni protecciones. Mantener
  Ubuntu y Windows y dos pasadas completas de la suite.
- No introducir hallazgos nuevos ni agravar otros en el diagnostico global.

## Examples
- Una modificacion staged del oraculo con checkout restaurado falla antes de
  ejecutar cualquier check y no modifica el indice ni HEAD.
- Un check que cambia el oraculo y falla produce rechazo de integridad.
- Dos checks correctos se ejecutan en orden dos veces en un repo Git real.

## Do / Don't
- DO usar repositorios y procesos reales y preservar sus resultados.
- DON'T ampliar permisos o mover la logica a otro archivo para eludir limites.

## Tests
El oraculo nuevo comprueba los cuatro presupuestos existentes y ejecuta Git y
checks reales, con aprobacion, rechazo de alias, alteracion staged, errores de
politica y revalidacion al fallar. Los oraculos previos permanecen congelados.

## Constraints
PARAR y reportar si se requiere cambiar oraculos anteriores sin revision,
runtime, workflows o protecciones, o si aparecen hallazgos nuevos o agravados.
