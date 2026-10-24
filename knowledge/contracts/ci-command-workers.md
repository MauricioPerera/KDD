---
type: 'Task Contract'
title: 'Paralelismo optativo del gate de comandos de contratos'
description: 'Ejecutar comandos independientes con concurrencia limitada conservando deduplicacion, scopes y fallos.'
tags: ['ci', 'performance', 'verification']
task: ci-command-workers
intent: 'Reducir el tiempo del gate ejecutando todos sus comandos con un pool acotado.'
target: scripts/validate_test_commands.py
language: python
signature: 'def run_all(contracts_dir, repo_root, timeout=180, deduplicate=False, workers=1) -> list:'
test_command: 'python -m unittest tests/test_ci_command_workers.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_ci_command_workers.py
tests_sha256: '37f2f9c9962b2107643b61e6f02dcfdb241556f5d71beabf28d09162118da19c'
touch_only: ['scripts/validate_test_commands.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [protocolo de tiempo total](../ci-runtime.md), extendiendo
[test-command-gate](test-command-gate.md) y
[deduplicacion](ci-execution-deduplication.md).

## Interface
- run_all agrega workers=1. Solo enteros1..8; bool y valores invalidos
  lanzan ValueError antes de ejecutar. CLI --workers N, default1, rechaza
  opciones invalidas antes de procesos o efectos.
- El opt-in workers>1 ejecuta hasta N comandos a la vez con el mismo cwd,
  entorno y timeout individual. No altera el comando ni la funcion
  run_test_command. Los consumidores son responsables de optar solo por
  comandos independientes; la plantilla no fuerza esa opcion en productos.
- deduplicate=True sigue agrupando solo strings identicos en esa llamada;
  ejecutar una vez y compartir exit/output/error con todos los contratos.
- Retorno por path, campos anteriores y scopes conservados; duracion solo
  en el representante, shared_from solo en sus referencias. El orden de
  salida no depende del orden de terminacion de los procesos.

## Invariants
Todos los comandos se ejecutan aunque otro falle. Cada contrato conserva
su veredicto; fallos de producto no quedan ocultos por infraestructura.
Timeout y ejecutable ausente siguen siendo FAIL, nunca SKIP. No guardar
cache entre invocaciones. workers1 mantiene el comportamiento anterior.
Respetar todas las [garantias del CI](../ci-runtime.md), incluyendo serial
por defecto en consumidores, matriz dual-OS, cuatro checks y suite2x.

## Examples
- Dos contratos, mismo comando, workers4 y deduplicate: un proceso, dos resultados.
- Tres comandos con workers2: hasta dos vivos; salida ordenada por path.
- Un exit3: sus referencias fallan; los otros comandos igualmente terminan.
- workers0: error sin crear archivos ni ejecutar comandos.

## Do / Don't
- DO: demostrar solapamiento con barreras de procesos y efectos reales.
- DON'T: confundir la suma de duraciones con el tiempo de pared del gate.

## Tests
Oraculo tests/test_ci_command_workers.py junto con los oraculos anteriores
de deduplicacion/gate, sin eliminar ninguna asercion. Comparacion real de
dos invocaciones, errores, cwd, scopes, orden y limite de procesos.

## Constraints
PARAR y reportar si se necesita omitir un comando, cambiar un oraculo no
revisado o modificar una proteccion remota.
Stdlib; sin red/LLM ni cambios de protecciones. No aumentar el timeout del
workflow ni introducir continue-on-error. Revision explicita del baseline.
