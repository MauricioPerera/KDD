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
tests_sha256: '1065d70d9c08371232bf3238022cdbbd92cd491fad25a67fa969cfda992956ab'
touch_only: ['scripts/mcp_gate_dispatch.py']
deps_allowed: ['mcp']
forbids: ['network', 'llm']
---

## Intent
Reservar el stdin del servidor [MCP](../mcp-server.md).

## Interface
El gate y el sello reciben EOF. Misma API y launcher contenido.

## Invariants
Mantener captura, plazos, rutas y protocolo de consola.

## Examples
- Unittest real pasa por stdio.
- El sello coincide y una ruta exterior se rechaza.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
SDK fijado y tuberias reales. El oraculo lee EOF.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
