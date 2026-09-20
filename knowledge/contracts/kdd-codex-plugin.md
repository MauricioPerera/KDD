---
type: 'Task Contract'
title: 'Plugin seguro de Codex para KDD'
description: 'Empaqueta el flujo KDD y eventos de ciclo de vida sin exponer el tablero ni secretos.'
tags: ['ccdd', 'codex', 'plugin', 'security']
task: kdd-codex-plugin
intent: 'Distribuir una integracion KDD para Codex basada en skill y hooks locales de entrega segura.'
target: plugins/kdd-codex/.codex-plugin/plugin.json
language: json
signature: 'name: kdd-codex'
test_command: 'python -m unittest tests/test_kdd_codex_plugin.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
tests: 'tests/test_kdd_codex_plugin.py'
tests_sha256: '150e5f663af859c94a1b6772c8888f572b931e76f83267ea8915486e61a45cc7'
touch_only: ['plugins/kdd-codex/**', '.agents/plugins/marketplace.json', 'knowledge/contracts/kdd-codex-plugin.md', 'knowledge/index.md', 'README.md']
deps_allowed: ['python', 'node']
forbids: ['llm']
---

## Intent

Conectar el flujo de [validacion](../validacion.md) a Codex sin convertir hooks en una frontera de privilegios.

## Interface

El plugin aporta una skill y hooks que solo entregan eventos a un relay HTTPS configurado explícitamente.

## Invariants

- El manifiesto no instala un servidor MCP ni abre un listener.
- Sin URL y secreto configurados, el relay no envía datos.
- Los hooks no aprueban herramientas ni cambian el resultado de Codex.

## Examples

- Sin variables de relay -> salida satisfactoria sin red.
- Evento Stop con relay configurado -> POST HTTPS firmado.

## Do / Don't

- DO: incluir identificador de sesión y evento, no prompts ni secretos.
- DON'T: exponer el tablero fuera de loopback.

## Tests

El oráculo comprueba el manifiesto, el hook y la política fail-closed del relay.

## Constraints

- PARAR y reportar si se necesita un endpoint HTTP, un token en argumentos o aprobación automática.
