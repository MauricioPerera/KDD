---
type: 'Task Contract'
title: 'Clasificacion Git para el flujo ligero de ODD'
description: 'Comprobar elegibilidad editorial de un candidato exacto sin conceder aprobacion.'
tags: ['odd', 'review', 'git', 'integration']
task: odd-lightweight
intent: 'Usar un flujo editorial recuperable y conservar la revision del baseline para cambios de garantias.'
target: scripts/baseline_review.py
signature: 'def inspect_small_change(repo_root, base_ref, candidate_ref, editorial_only=False):'
test_command: 'python -m unittest tests.test_odd_lightweight'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 40
  params_max: 4
tests: tests/test_odd_lightweight.py
tests_sha256: 'f70d8929316ebb1db5bead3f77327618c39407f2f6adeff0f57702beab9a53e6'
oracle_files: ['tests/test_odd_lightweight.py', 'tests/test_baseline_risk_review.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/baseline_review.py', '.agents/AGENTS.md', 'knowledge/metodologia-ejecucion.md']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

Aplicar el [flujo ligero](../odd-lightweight.md) de forma opt-in. La inspeccion
conserva la [revision proporcional](../baseline-risk-review.md) y la
[aprobacion](../quality-approval.md) del baseline.

## Interface

`inspect_small_change(repo_root, base_ref, candidate_ref, editorial_only=False)`
recibe un booleano y devuelve los campos de `inspect_change` mas `route` y
`reason`. Acepta exclusivamente OID nativos completos de commits con
historia completa y base ancestro estricto, igual que `inspect_change`.

La CLI expone `--small-change` en `baseline_review.py`. `--editorial-only`
requiere ese modo y `--review` es incompatible con el. Los modos historicos
conservan sus argumentos, resultados y codigos. Exit 0 indica una clasificacion
completa, exit 2 un error sin JSON. `review_ready` queda en false y no hay
`approved_ref` ni permiso de fusion.

Evaluar en este orden:

| Condicion | Route | Reason |
| --- | --- | --- |
| Candidato cuyo unico padre real difiere de la base, o merge | `standard` | `history` |
| Diff vacio | `standard` | `empty_change` |
| Piso distinto de low, ruta fuera del perimetro editorial, alta, baja o modo distinto de 100644 en cualquier lado | `standard` | `outside_scope` |
| Falta la confirmacion editorial | `standard` | `confirmation_required` |
| Cumple todas las condiciones | `lightweight` | `editorial_only` |

El perimetro de rutas es exacto y sensible a mayusculas. Las guias bajo
`docs/guides/` deben terminar en `.md` y sus componentes no pueden empezar
por punto. Renombres se revisan como baja y alta. Un cambio de garantias
requiere baseline aunque afecte una ruta editorial. La confirmacion es una
declaracion explicita del operador sobre contenido y politica, que Git no
puede comprobar por si mismo.

## Invariants

- Leer el diff y el padre real de objetos Git sin sustituciones, sin checkout,
  sin ejecutar contenido candidato y sin escribir referencias, indice,
  configuracion o working tree. Ignorar cambios locales al inspeccionar el
  commit y conservar su identidad en el resultado.
- El flujo ligero es una clasificacion local y no modifica gates, registro
  de aprobaciones, workflow, runtime ni protecciones. Conservar Ubuntu y
  Windows y las dos pasadas completas de la suite.
- Reusar la lectura y el piso de riesgo de `inspect_change`.

## Examples

- Una correccion editorial confirmada en el README, en un solo commit, es
  `lightweight`.
- La misma correccion junto con un cambio de prueba es `standard` por
  `outside_scope`.
- Dos commits que cambian y restauran codigo devuelven `standard` por
  `history`, incluso si el diff final solo muestra el README.

## Do / Don't

- Confirmar la intencion editorial y la politica aplicable antes de
  indicar `--editorial-only`.
- Mantener los controles de aprobacion y CI independientes del resultado
  del clasificador.

## Tests

Ejecutar Git y la CLI real en proyectos descartables. Cubrir una guia y el
README, declaracion ausente, mezclas con contratos/oraculos/politica/workflow
o codigo, archivos de evidencia, modos, altas y bajas, historia intermedia,
reemplazos, aliases, salida de revision y ausencia de escrituras.
El inventario conserva los 2187 IDs anteriores.

## Constraints

PARAR y reportar si el cambio altera una garantia, un oraculo o una politica
sin el baseline requerido.
Aplicar la [revision proporcional](../baseline-risk-review.md) al commit que
introduce este contrato y su oraculo antes de implementar la clasificacion.
