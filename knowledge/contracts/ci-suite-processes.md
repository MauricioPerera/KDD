---
type: 'Task Contract'
title: 'Suite completa con procesos acotados e inventario verificable'
description: 'Ejecutar todos los casos unittest con paralelismo por modulo sin perder casos ni ocultar fallos.'
tags: ['ci', 'performance', 'verification']
task: ci-suite-processes
intent: 'Reducir la duracion de cada pasada conservando sus IDs y resultados reales.'
target: scripts/run_test_suite.py
language: python
signature: 'def run_suite(start_dir, pattern="test_*.py", workers=1) -> dict:'
test_command: 'python -m unittest tests/test_ci_suite_processes.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_ci_suite_processes.py
tests_sha256: '49a501dac3d4a3deb928f88d881a10cb90f0df0e4fe379a65f3067ce67ae9362'
touch_only: ['scripts/run_test_suite.py', 'scripts/guard_pr_baseline.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [protocolo y medicion de tiempo total](../ci-runtime.md),
conservando [validacion](../validacion.md) y [aprobacion](../quality-approval.md).

## Interface
- run_suite(start_dir, pattern='test_*.py', workers=1) devuelve dict version1.
- CLI --start-directory (default tests), --pattern (default test_*.py),
  --workers (entero1..8, default1) y --report-json PATH opcional.
  El cwd del hijo es el cwd original. Rutas con espacios/Unicode son validas.
- workers1 ejecuta la suite completa con la semantica serial unittest.
  workers>1 descubre el inventario completo y despacha modulos completos
  en procesos independientes, maximo workers vivos, incluyendo paquetes.
- Reporte: version=1, ok, tests_run, expected_ids, executed_ids, skipped,
  failures, errors, expected_failures y unexpected_successes. Las listas
  de resultados contienen objetos con id; skipped conserva reason.
  Los IDs esperados/ejecutados se ordenan para comparar; hay tiempos y
  evidencia de modulos. Reporte escrito incluso en un fallo controlado.
- validate_report(expected_ids, report) -> list de errores de integridad:
  rechaza schema incompleto, cuentas falsas, faltantes, duplicados, IDs
  ajenos o un ok:true que contradice failures/errors/unexpected_successes.
- Exit0 requiere inventario no vacio, ejecucion exacta, todos los hijos
  terminados con exit0 y sin fallos de integridad/comportamiento; resto exit1.
  Opciones invalidas devuelven no cero antes de ejecutar tests.

## Invariants
Conservar todos los [criterios normativos](../ci-runtime.md), sin cache de
resultados ni skips nuevos. No interpretar texto PASS/FAIL del stdout como
evidencia. Un hijo que aborta incluso con exit0 sin reporte es fallo.
No compartir cwd/entorno mutable entre modulos concurrentes en hilos.
Agregar scripts/run_test_suite.py a PROTECTED_FILES del guard confiable;
no cambiar ninguna otra regla de confianza ni ejecutar el candidato en el guard.
Las dos pasadas del workflow son identicas y consecutivas; default seguro
serial para consumidores, cuatro procesos solo en KDD nativo u opt-in.

## Examples
- Dos modulos esperando una barrera: ambos procesos deben estar vivos.
- Cuatro modulos y workers2: como maximo dos intervalos se solapan.
- os._exit(0) dentro de un test: falta reporte, runner falla.
- Mismos IDs otra invocacion: se ejecutan otra vez y generan evidencia nueva.

## Do / Don't
- DO: cotejar IDs con unittest y probar procesos reales en temporales.
- DON'T: reducir cobertura, filtrar casos lentos o acreditar reporte incompleto.

## Tests
Oraculo tests/test_ci_suite_processes.py: inventario, fixtures, resultados,
procesos, aislamiento, fallos, segunda pasada, validacion de reportes y CI.
La medicion de rendimiento se registra aparte del veredicto de correccion.

## Constraints
PARAR y reportar si se necesita reducir casos, agregar skips, cambiar un
oraculo no revisado o modificar una proteccion remota.
Solo stdlib. No cambiar protecciones, pins, permisos ni calidad de producto.
Cambios adicionales de oraculo requieren revision; budget declarativo sin Nivel2.
