---
type: 'Task Contract'
title: 'Herramienta de benchmark de gates y suite'
description: 'Mide los gates de nivel 1 (GATES derivada de mcp_gate_dispatch.LEVEL1_GATES, nunca hardcodeada) y la suite de tests con logica de orquestacion pura (min/mediana/max, formato, exit code) resuelta por inyeccion de run_fn/timer_fn; solo el CLI real usa subprocess/reloj de pared. Diagnostico de mantenimiento, no gate de CI.'
tags: ['ccdd', 'benchmark', 'mantenimiento', 'infra']

task: benchmark-gates
intent: "Medir el tiempo de los gates de nivel 1 (derivados de mcp_gate_dispatch.LEVEL1_GATES) y la suite, con orquestacion pura y testeable por inyeccion de dependencias."
target: scripts/benchmark_gates.py
signature: "def benchmark_gates(gates, suite_cmd, repo_root, run_fn, timer_fn, reps=3, warmup=1, suite_passes=2) -> dict"
test_command: "python -m unittest tests/test_benchmark_gates.py"
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_benchmark_gates.py"
tests_sha256: "6a08ba940b171c2630efe9020ae1bd8ec6efc5af69fd0e3cbcf66e888ec5f0ac"
touch_only: ['scripts/benchmark_gates.py']
deps_allowed: []
forbids: ['network', 'llm']
---

# Contract: Herramienta de benchmark (benchmark_gates)

## Intent
Formalizar como activo versionado el benchmark ad-hoc corrido a pedido del
usuario: medir los gates de nivel 1 + la suite, con la orquestación (conteo
de reps, descarte de warmup, min/mediana/max, formato del reporte, exit code)
implementada como funciones PURAS testeables por inyección de dependencias —
nunca fosiliza números de una corrida particular en la documentación del repo.
Spec: `specs/CONTRACT-29-benchmark-gates.md`.

Revisión estructural (post #71): `GATES` era una tupla explícita mantenida a
mano, alineada "a ojo" con `mcp_gate_dispatch.LEVEL1_GATES` — quedó
desactualizada dos veces (primero faltaban `validate_test_commands`/
`scan_secrets`, AUDIT-01 H-5; después `validate_security_findings`, #69/#70).
`GATES` ahora se DERIVA de `mcp_gate_dispatch.LEVEL1_GATES` vía `build_argv`,
mismo patrón que `preflight.ALL_GATES` — un gate nuevo en `GATE_SPECS`
aparece acá solo con actualizar el dispatch, sin tocar este archivo.

## Interface
- `measure_repeated(cmd, cwd, run_fn, timer_fn, reps=3, warmup=1) -> dict`
- `measure_suite(cmd, cwd, run_fn, timer_fn, passes=2) -> dict`
- `benchmark_gates(gates, suite_cmd, repo_root, run_fn, timer_fn, reps=3, warmup=1, suite_passes=2) -> dict`
- `count_errors(report) -> int`
- `format_report(report) -> str`
- `main(argv, run_fn=None, timer_fn=None, gates=None, suite_cmd=None) -> int`
- Semántica EXACTA de cada función, contratos de `run_fn`/`timer_fn`, formato
  del reporte y flags del CLI: docstring del oráculo congelado
  `tests/test_benchmark_gates.py`.
- `GATES`: constante módulo, tupla de `(name, cmd)` derivada de
  `mcp_gate_dispatch.LEVEL1_GATES` (todos los gates de CI salvo
  `validate_attestation`, local-only) vía `mcp_gate_dispatch.build_argv(name, {})`
  para cada `cmd` — mismo orden que `knowledge/validacion.md`. `SUITE_CMD`:
  constante módulo con el comando de la suite completa.

## Invariants
- `measure_repeated`, `measure_suite`, `benchmark_gates`, `count_errors`,
  `format_report` son PURAS: `run_fn`/`timer_fn` SIN default (obligatorios),
  nunca invocan `subprocess.run(` ni `time.perf_counter(` directamente.
- Solo `main` (cuando `run_fn`/`timer_fn` son `None`) construye las
  implementaciones reales (`subprocess.run` + `time.perf_counter`) — la única
  rama con efecto de lado, y la única no cubierta por el oráculo.
- `deps_allowed: []`: `subprocess`, `time`, `statistics`, `sys` (stdlib) +
  `mcp_gate_dispatch` (módulo hermano de `scripts/`, sin dependencia externa
  -- mismo criterio que ya usa `preflight.py` para importar el mismo módulo).
  Ningún paquete de PyPI.
- Mensajes/output ASCII; determinismo garantizado dado el mismo `run_fn`/
  `timer_fn`.

## Examples
- `measure_repeated(["cmd"], "/repo", run_fn, timer_fn, reps=3, warmup=1)` con
  timestamps `[0,1, 10,10.5, 20,20.3, 30,30.7]` -> `times=[0.5,0.3,0.7]`,
  `min=0.3`, `median=0.5`, `max=0.7`.
- `format_report(...)` con 2 gates + suite de 2 pasadas -> string exacto (ver
  `TestFormatReport.test_formato_exacto` en el oráculo).

## Do / Don't
- DO: derivar `GATES` de `mcp_gate_dispatch.LEVEL1_GATES` (nunca hardcodear
  nombres/argv de gates aparte) — la excepción deliberada al estilo general
  de `scripts/` (constantes explícitas, sin heurísticas), justo porque una
  lista de gates explícita y separada ya demostró (dos veces) que se
  desincroniza.
- DON'T: editar `tests/test_benchmark_gates.py` SIN re-sellar `tests_sha256`
  (`python scripts/validate_contracts.py --hash tests/test_benchmark_gates.py`)
  en el mismo cambio. El oráculo puede evolucionar cuando el alcance real del
  contrato cambia (p.ej. un gate nuevo en `GATE_SPECS`); lo que no se permite
  es una edición silenciosa sin re-sellar.
- DON'T: agregar un paso de CI en `.github/workflows/validate.yml` (decisión
  del spec: es diagnóstico, no gate de corrección).
- DON'T: llamar `subprocess.run`/`time.perf_counter` fuera de `main`.

## Tests
`python -m unittest tests/test_benchmark_gates.py` verde SIN modificar el
oráculo; ninguna aserción dispara un subprocess real ni depende del reloj
(verificado estructuralmente por `TestConstantes` del propio oráculo). Suite
completa sin regresiones.

## Constraints
- Tocar SOLO: `scripts/benchmark_gates.py`. Reporte local en
  `.agents/logs/C29-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: el oráculo exigiera comportamiento contradictorio; la
  separación pura/efecto-de-lado no pudiera sostenerse sin duplicar lógica
  entre `main` y las funciones inyectables; o el budget de complejidad no
  alcanzara sin romper un test.
