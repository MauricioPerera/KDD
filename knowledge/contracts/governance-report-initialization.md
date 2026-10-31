---
type: 'Task Contract'
title: 'Inicializacion compatible con el reporte de cierre de gobierno'
description: 'Inicializacion compatible con el reporte de cierre de gobierno con alcance mecanico y revision humana explicitos.'
tags: ['governance', 'provenance', 'verification']

task: governance-report-initialization
intent: 'Inicializacion compatible con el reporte de cierre de gobierno.'
target: scripts/init_project.py
signature: 'def init_project(repo_dir, apply, name, repository=None) -> dict:'
test_command: 'python -m unittest tests.test_governance_report_initialization'
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_governance_report_initialization.py
tests_sha256: 'da49b320a57e1b5b21664396682f08eaae55080c24acdd926d0d172eac499dec'
touch_only: ['scripts/init_project.py']
deps_allowed: ['stdlib', 'bootstrap_transaction']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Cumplir la [propuesta de contexto y aprendizaje](../context-learning-provenance.md)
y el [objetivo](../kdd-governance-closure.md), conservando la
[aprobacion](../quality-approval.md) y sus limites de confianza.

## Interface

Conservar API/CLI y manifiestos previos. Extender solo la limpieza opcional de
la ruta exacta docs/reports/CONTRACT-34-REPORT.md, cuando exista. No exigirla
antes del cierre real ni descubrir permisos por glob.

## Invariants

- Presente regular -> plan una sola vez y retiro con la spec 34, dentro de transaccion.
- Ausente -> no bloquear ni inventar un reporte o cierre historico.
- No regular/alias o falta otra entrada requerida -> abortar antes de cambiar archivos.
- Preservar reportes ajenos, 33 pares historicos, digests, prechecks y rollback.
- Revision exacta del oraculo test_init_project: conjunto eliminado, conteo de
  reportes y pertenencia historica admiten solo el reporte 34 opcional. Conservar
  todos los IDs, metodos y demas aserciones; actualizar solo su sello en el contrato.

## Examples

- Reporte 34 sintetico presente -> plan y apply lo retiran, sin huerfano.
- Reporte 34 ausente -> inicializar; reporte 35 propio -> conservar bytes.
- Directorio en ruta del reporte -> rechazo previo sin borrar otros archivos.

## Do / Don't

- DO conservar evidencia real, versiones y alcance observado.
- DON'T presentar una identidad o referencia como comprension, semantica o ejecucion.

## Tests

Oraculo nuevo tests/test_governance_report_initialization.py con filesystem/Git reales. La extension de
inicializacion revisa unicamente las tres expectativas exactas documentadas
del oraculo anterior; los demas contratos y tests congelados se conservan.

## Constraints

PARAR y reportar si hace falta otra fuente, oraculo, dependencia, ampliar budgets,
modificar workflows/protecciones o la confianza del runner. Aprobar baseline
antes de implementar y esperar el CI dual-OS 2x de KG-4. No inferir aprobacion
humana ni certificacion retrospectiva de ejecucion o comprension.
