---
type: 'Task Contract'
title: 'Timeout con cancelacion del arbol de procesos'
description: 'No permitir descendientes activos ni pipes sin limite despues de un timeout.'
tags: ['processes', 'reliability', 'integration']
task: process-tree-timeout
intent: 'Contener, cancelar y esperar los procesos de cada comando con deadline.'
target: scripts/process_tree.py
language: python
signature: 'def run(argv, *, cwd, timeout, **kwargs):'
test_command: 'python -m unittest tests/test_process_tree_timeout.py'
budget:
  cyclomatic_max: 18
  nesting_max: 4
tests: tests/test_process_tree_timeout.py
tests_sha256: 'c8de0b40f8b8d80d8b7aa5e07c93ea5bce240cc1d58c5b9efbaa1783e516cf18'
touch_only: ['scripts/process_tree.py', 'scripts/validate_test_commands.py', 'scripts/preflight.py', 'scripts/mcp_gate_dispatch.py', 'scripts/task_evidence.py', 'scripts/run_test_suite.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar [cancelacion y limites](../ci-audit-remediation.md) a comandos de
contratos, preflight, MCP y evidencia de tareas, conservando sus errores publicos.

## Interface
- run recibe argv lista, cwd y timeout positivo finito; admite capture_output,
  text, encoding, errors, env y stdin usados por los callers. Devuelve
  subprocess.CompletedProcess o lanza TimeoutExpired/FileNotFoundError/OSError.
- Timeout cubre lanzamiento y espera. Contencion antes del objetivo, cancelacion
  de descendientes y drenaje acotado (gracia maxima de 5 s); no usa shell.
- Los adaptadores conservan exit_code=None/error=timeout o TASK_TESTS; no
  convierten una limpieza incompleta en exito. Fallos de contencion son errores.
- Los recursos del SO se liberan en exito, fallo y timeout. Una ejecucion no
  cancela procesos de otra invocacion concurrente ni del propio test padre.

## Invariants
Las [limitaciones de contencion](../ci-audit-remediation.md) son explicitas.
Usar grupo de proceso POSIX / Job Object Windows sin carrera antes de crear hijos.
Con stdout redirigido o heredado, hijo y nieto no escriben despues del retorno
por timeout. No ignorar errores de limpieza ni dejar handles de Jobs abiertos.
Los callers mantienen outputs Unicode, cwd, env y codigos de salida reales.

## Examples
- Padre duerme, hijo/nieto intentan escribir: timeout rechaza y ningun marcador
  posterior aparece con el proceso ya terminado.
- Hijo hereda pipes: timeout no espera indefinidamente a communicate.
- Una invocacion vecina sana termina y conserva su output mientras otra expira.

## Do / Don't
- DO: coordinar hijos con handshake observable antes de probar timeout.
- DON'T: simular PIDs/procesos ni usar taskkill de alcance global.

## Tests
tests/test_process_tree_timeout.py usa procesos e interpretes reales, verifica
descendientes, ausencia de escrituras tardias, pipes, retorno acotado, Unicode,
exit no cero y adaptadores de contratos/preflight/MCP/tareas en fixtures aislados.
La [precondicion observable](../process-fixture-readiness.md) separa el arranque
real de la verificacion de cancelacion, con control negativo sin contencion.

## Constraints
PARAR y reportar si el SO no permite establecer contencion antes del objetivo.
No agregar dependencia externa, skip por SO ni nueva excepcion de calidad.
La gracia de limpieza no aumenta el tiempo de ejecucion permitido al objetivo.
