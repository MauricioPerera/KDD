---
type: 'Task Contract'
title: 'Perfil medible de suite post inicializacion'
description: 'Conservar la integracion completa y limitar su latencia sin alterar las dos suites de CI.'
tags: ['bootstrap', 'ci', 'performance', 'integration']
task: init-post-apply-profile
intent: 'Ejecutar post-apply con inventario completo y un perfil nativo explicito.'
target: scripts/init_post_apply_suite.py
signature: 'python scripts/init_post_apply_suite.py --repo-root DIR [--report-json FILE]'
test_command: 'python -m unittest tests.test_init_post_apply_profile'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_init_post_apply_profile.py
tests_sha256: '5f155adeaafe2f5c3baaad30d2daf7d6d126585b6e64e0c2eab98da4d550f118'
touch_only: ['scripts/init_post_apply_suite.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la medicion de [remediacion de auditoria](../audit-p1-p2-remediation.md)
a la integracion completa de [init-project](init-project.md).

## Interface
CLI que ejecuta `scripts/run_test_suite.py` del proyecto indicado con cwd en
ese proyecto, tests/test_*.py y seis procesos Windows o cuatro Ubuntu. Acepta
un reporte JSON opcional nuevo, preserva stdout/stderr y devuelve el exit real.

## Invariants
- El fixture aprobado conserva su copia real, apply, gates, asserts y todos los
  IDs post-init; solo cambia la seleccion nativa del perfil. Sin nuevos SKIP.
- Las dos suites ordinarias de CI siguen completas, independientes y con sus
  perfiles vigentes; no variar el timeout 600 ni permitir exito al fallar el hijo.
- Si el reporte ya existe, rechazar sin modificarlo. No usar shell ni red.
- Medir varias muestras comparables; seis procesos son una hipotesis de prueba,
  no evidencia de mejora ni garantia de pasar en todos los runners.

## Examples
- Dos modulos reales pasan con IDs identicos y perfil del SO.
- Un hijo falla o el reporte existe -> fallo sin sustituirlo.

## Do / Don't
- DO conservar controles de integridad y todas las pruebas existentes.
- DON'T contar el perfil como optimizacion hasta medirlo en CI comparable.

## Tests
`tests/test_init_post_apply_profile.py` ejecuta procesos e inventario reales en
un proyecto temporal, con control sano y uno fallido. El cambio del fixture
anterior y su sello se presentan en el mismo baseline para revision humana.

## Constraints
PARAR y reportar si se necesita cambiar una proteccion remota o aprobar runtime.
No modificar timeouts, matriz, limites de presupuestos ni runtime confiable.
Si mediciones no demuestran mejora o aparecen errores, conservar evidencia y
reconsiderar perfil; no afirmar que el problema esta resuelto.
