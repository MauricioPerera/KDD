---
type: 'Task Contract'
title: 'Perfil compartido de limites y scheduling de gates'
description: 'Alinear CLI, preflight, MCP y CI con opciones tipadas y defaults seguros.'
tags: ['ci', 'mcp', 'reliability']
task: gate-execution-profile
intent: 'Evitar timeouts locales obsoletos sin quitar limites ni paralelizar consumidores implicitamente.'
target: scripts/execution_profile.py
language: python
signature: 'def resolve_profile(**overrides) -> dict:'
test_command: 'python -m unittest tests/test_gate_execution_profile.py'
budget:
  cyclomatic_max: 12
  nesting_max: 3
tests: tests/test_gate_execution_profile.py
tests_sha256: '169aab4afa54ab5c638bbbadd8c58cae4d4a27b367eb4223535c093a70f34f37'
touch_only: ['scripts/execution_profile.py', 'scripts/preflight.py', 'scripts/mcp_gate_dispatch.py', 'scripts/mcp_server.py', 'scripts/validate_test_commands.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [perfil compartido](../ci-audit-remediation.md) a
[preflight](preflight.md), [dispatch](mcp-gate-dispatch.md) y
[comandos](test-command-gate.md), sin cambiar el conteo de gates.

## Interface
- resolve_profile(**overrides) devuelve command_timeout=600, gate_timeout=1800,
  workers=1, deduplicate=True. Rechaza claves desconocidas, bool como numero,
  NaN/infinito/no positivo, workers no entero1..8 y deduplicate no bool.
  gate_timeout debe ser mayor que command_timeout; ambos son ajustables.
- run_preflight agrega kwargs command_timeout, gate_timeout, workers, deduplicate;
  CLI --command-timeout, --gate-timeout, --workers, --no-deduplicate. Contract
  ejecuta con command_timeout, full despacha comandos con esas opciones y limite
  agregado; gates simples conservan120. Default serial fuera del opt-in de CI.
- build_argv('validate_test_commands', params) conserva posicionales y agrega
  --timeout, --workers y --deduplicate cuando corresponda. run_gate(timeout=None)
  selecciona limite del perfil; timeout explicito conserva su funcion de deadline.
- La tool MCP validate_test_commands expone las cuatro opciones tipadas y
  mantiene confinamiento de paths. Numeros/booleanos no se interpretan como rutas;
  claves desconocidas y opciones invalidas se rechazan antes de ejecutar.
- validate_test_commands API/CLI adopta600 como default por comando. --timeout
  existente sigue admitido; workers1/deduplicateFalse explicitos siguen disponibles.

## Invariants
Los [criterios de CI](../ci-audit-remediation.md) se conservan. No usar cache de
resultados ni ejecutar gates recursivamente desde las pruebas. Parametros se
pasan como argv, sin shell ni interpolacion de codigo. Fallos y timeout siguen
siendo fallos; ninguna configuracion desactiva [cancelacion](process-tree-timeout.md).

## Examples
- Default MCP: comandos con timeout600, deduplicados y workers1; deadline1800.
- Perfil con command_timeout=.5, gate_timeout=10: comando sano de .2 s pasa
  realmente por preflight y MCP; uno colgado falla y sus hijos terminan.
- workers='$(echo bad)' o gate_timeout infinito: rechazo sin efectos del objetivo.

## Do / Don't
- DO: probar fixtures reales lentos/cortos con limites pequenos y comparar argv.
- DON'T: esperar600 s en tests para demostrar que se propaga la configuracion.

## Tests
tests/test_gate_execution_profile.py comprueba defaults, validacion, integracion
real de preflight/dispatch, resultados no cero, deduplicacion, paths con espacios,
limites y ausencia de efectos ante opciones invalidas. Se adaptan unicamente
expectativas obsoletas de limites/argv en los dos oraculos anteriores.

## Constraints
PARAR y reportar si hay que modificar protecciones, SDK/pins o eliminar cobertura.
Mantener las dos matrices, ambas pasadas identicas, permisos y cuatro jobs.
