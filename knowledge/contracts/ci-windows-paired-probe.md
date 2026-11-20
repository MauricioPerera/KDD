---
type: 'Task Contract'
title: 'Ensayo pareado Windows'
description: 'Comparar las dos pasadas en una VM.'
tags: ['ci', 'performance', 'windows', 'integration']
task: ci-windows-paired-probe
intent: 'Medir las dos pasadas con VM y runtime comunes.'
target: scripts/ci_windows_paired.py
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests.test_ci_windows_paired_probe'
test_runner: python-unittest
test_scope: infrastructure
tests: tests/test_ci_windows_paired_probe.py
tests_sha256: 'c3105df68fe724b974b45661e80532d8fe7230aae61b0e3ce23304acd090bcfd'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
oracle_files: ['tests/test_ci_windows_paired_probe.py', 'tests/__init__.py']
touch_only: ['scripts/ci_windows_paired.py', '.github/workflows/windows-suite-paired-probe.yml']
deps_allowed: ['stdlib', 'git', 'trusted_ci', 'coverage']
forbids: ['llm']
---

## Intent
Comparar revisiones del [CI Windows](ci-windows-board-routing.md).

## Interface
`python -I scripts/ci_windows_paired.py --plan PLAN.json --output DIR`.
Plan v1 con schema_version, order, runtime_ref, bundle y arms. Cada rol
reference/candidate declara checkout, commit, tree e ids_sha256 (IDs
ordenados con LF final).
Por rol emitir suite-1.json, suite-2.json y coverage/coverage.json.
comparison.json contiene order, runtime_ref y arms por rol con commit, tree
y passes (number, duration_seconds de suite completa, ids_sha256, coverage bool).

## Invariants
- Verificar commit, tree y Git limpio antes y despues. Cotejar bundle y
  runtime_ref antes de ejecutar. Checkouts, salida nueva y temporales por brazo disjuntos.
- trusted_ci ejecuta order. Invertir orden en otro ensayo alojado. Dos pasadas
  consecutivas por brazo, seis workers, KDD_SKIP_INIT_POST_APPLY_SUITE=1.
- Limpiar COVERAGE_*. Medir cobertura solo en pasada 1 con ci_coverage.py y
  cotejar su SHA. expected_ids y executed_ids de cada pasada cumplen digest y
  cero omisiones. Candidato incluye todos los IDs base.
- Exito completo publica comparison.json. Conservar evidencia parcial ante
  PAIRED_OUTPUT, PAIRED_CHECKOUT, PAIRED_RUNTIME, PAIRED_SUITE,
  PAIRED_COVERAGE o PAIRED_INVENTORY.

## Examples
- Candidato agrega un caso.
- Orden inverso conserva IDs.

## Do / Don't
Fijar commits, toolchain y locks. Contar procesos y medir latencia de
arranque Git/Python con igual metodo.

## Tests
Git y unittest reales. Auxiliar sintetico para secuencia y SHA de cobertura.

## Constraints
PARAR y reportar si falta aprobar baseline o workflow aislado de solo lectura.
Separar del check y recibos oficiales.
