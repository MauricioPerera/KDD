---
type: 'Task Contract'
title: 'Plugin seguro de Codex para KDD'
description: 'Empaqueta el flujo KDD como una skill local sin exponer datos ni secretos.'
tags: ['ccdd', 'codex', 'plugin', 'security']
task: kdd-codex-plugin
intent: 'Distribuir una integracion KDD para Codex basada solo en una skill local.'
target: plugins/kdd-codex/.codex-plugin/plugin.json
language: json
signature: 'name: kdd-codex'
test_command: 'python -m unittest tests/test_kdd_codex_plugin.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
tests: 'tests/test_kdd_codex_plugin.py'
tests_sha256: 'f3d59b45a43d0dee16a8b8084dabd398e2f959c4f0afc8b8cb854efbfa9c675e'
touch_only: ['plugins/kdd-codex/**', '.agents/plugins/marketplace.json', 'knowledge/contracts/kdd-codex-plugin.md', 'knowledge/index.md', 'README.md']
deps_allowed: ['python', 'node']
forbids: ['llm']
---

## Intent

Conectar el flujo de [validacion](../validacion.md) a Codex mediante una skill
local, sin crear una frontera de red o privilegios.

## Interface

El plugin aporta una skill local. No registra hooks, servidores MCP, listeners,
servicios ni conexiones externas.

## Invariants

- El manifiesto no instala un servidor MCP, hooks ni abre un listener.
- La skill no transmite datos ni solicita secretos.
- La skill no aprueba herramientas ni cambia el resultado de Codex.

## Examples

- Ejecutar el flujo KDD -> salida satisfactoria sin red.
- Solicitar entrega remota -> remitirse a una integración futura revisada.

## Do / Don't

- DO: usar los contratos y validadores locales del repositorio.
- DON'T: configurar hooks, relay, envío de eventos ni acceso al tablero.

## Tests

El oráculo comprueba que el manifiesto y la estructura publicada sean solo-skill.

## Constraints

- PARAR y reportar si se necesita un endpoint HTTP, un token en argumentos,
  hooks o aprobación automática.
