---
type: 'Task Contract'
title: 'Aislamiento de stdin en MCP stdio'
description: 'Separar la entrada de los validadores hijos del transporte MCP para que respondan en Windows y Ubuntu.'
tags: ['mcp', 'windows', 'integration']
task: mcp-stdio-child-input
intent: 'Aislar el stdin de los validadores y del sellador lanzados por MCP stdio.'
target: scripts/mcp_gate_dispatch.py
signature: "def run_gate(tool_name, params, repo_root='.', timeout=None)"
test_command: 'python -m unittest tests.test_mcp_stdio_child_input'
test_runner: python-unittest
oracle_files: ['tests/test_mcp_stdio_child_input.py', 'tools/mcp-sdk/pins.json']
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: 'tests/test_mcp_stdio_child_input.py'
tests_sha256: 'fd8a2fee0a76d8261773bd21ca7c6d24e5eca7171a979acd0c1413258bb4677d'
touch_only: ['scripts/mcp_gate_dispatch.py']
deps_allowed: ['mcp']
forbids: ['network', 'llm']
---

## Intent
El [servidor MCP](../mcp-server.md) recibe JSON-RPC por stdin. El validador
hijo y el proceso que calcula el sello deben recibir EOF por su propia entrada.
El [despacho](mcp-gate-dispatch.md) conserva el lanzador contenido y su perfil.

## Interface
Los consumidores actuales siguen invocando run_gate y seal_tests igual.
Por stdio real, el SDK fijado inicia el servidor y el cliente recibe el
resultado del mismo gate y del mismo calculo de sello que por CLI.

## Invariants
La tuberia JSON-RPC queda reservada al servidor. Se preservan los limites,
la contencion de arboles de procesos, la captura de stdout y stderr, todos
los campos de respuesta y el confinamiento de rutas. El perfil nativo de
CI ejecuta la prueba con el SDK fijado, sin omisiones.

## Examples
- Un contrato temporal ejecuta su unittest y devuelve exit_code 0.
- Sellar un oraculo en el proyecto devuelve su SHA-256.
- Una ruta exterior devuelve exit_code 2 sin devolver un hash.

## Do / Don't
- DO: reutilizar subprocess.DEVNULL en los dos puntos de despacho.
- DON'T: cerrar la entrada del servidor, cambiar los plazos ni sustituir stdio por un transporte en memoria.

## Tests
El oraculo abre dos sesiones sobre tuberias reales con el servidor FastMCP
fijado. Usa un directorio desechable y ejecuta un unittest y el sello real.
La aplicabilidad sin SDK conserva el perfil optativo fuera del CI nativo.

## Constraints
PARAR y reportar si hace falta cambiar el runtime confiable, el SDK fijado,
los workflows o las protecciones. Aprobar el baseline antes de implementar.
