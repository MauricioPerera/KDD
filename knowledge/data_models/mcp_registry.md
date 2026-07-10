---
type: 'Data Model'
title: 'Registro de servidores MCP'
description: 'Política de un registro MCP commiteable como rule contract: transportes válidos, stdio exige command, streamable-http exige url https, nombres kebab-case y — la regla central — secretos SOLO como referencias ${VAR}, nunca literales. Séptimo dominio de la vertiente; motivó la familia matches.'
tags: ['mcp', 'registry', 'rules', 'seguridad', 'example']
---

# Registro de servidores MCP (dominio de ejemplo)

Política determinista para un registro de servidores MCP que se COMMITEA (por ejemplo el
`.mcp.json` de un proyecto compartido). Procedencia: la forma real de un registro de
Claude Code (`mcpServers`), observada en un RECON sobre una config real que tenía
contraseñas literales en `env` — exactamente lo que esta política prohíbe en un archivo
versionado. El ejemplo del repo es SINTÉTICO: ningún dato real se comitea.

## Formato del record (forma auditoría, aplanado)

```json
{
  "servers": [
    {"name": "vps", "transport": "stdio", "command": "node"},
    {"name": "n8n", "transport": "streamable-http", "url": "https://..."}
  ],
  "env_entries": [
    {"server": "vps", "key": "VPS_PASSWORD", "value": "${VPS_PASSWORD}"}
  ]
}
```

`env` se aplana a `env_entries` (una entrada por par servidor/clave) porque `each` opera
sobre UNA colección plana — no se agregan colecciones anidadas sin evidencia (doctrina).

## Reglas (examples/rules/mcp-registry.rules.json)

- `servers` presente.
- Por servidor (`each servers`): `name` y `transport` presentes; `transport` en
  `{stdio, streamable-http, sse}`; `name` kebab-case (`matches`).
- `each servers where transport=stdio`: `command` presente.
- `each servers where transport=streamable-http`: `url` presente y `matches ^https://`.
- Por entrada de entorno (`each env_entries`): `value` debe matchear
  `^\$\{[A-Z_][A-Z0-9_]*\}$` — **un secreto literal en un registro commiteable es una
  violación**, la referencia se resuelve en runtime fuera del repo.

La regla de secretos y la de kebab son propiedades de TEXTO: la clase que el dominio
editorial ([Contrato 23](../../docs/reports/CONTRACT-23-REPORT.md)) midió y dejó como
frontera. Su segunda aparición aquí habilitó la familia `matches` según la doctrina
evidencia-primero de [rule-contract-spec](../rule-contract-spec.md).

## Fronteras (honestas)

- **Servidor vivo** (`code_only`, razón documentada en el rule-set): handshake, catálogo
  real de tools, latencia y comportamiento exigen RED — fuera del nivel 1 por doctrina.
  Si algún día se contrata, es task contract de integración, no regla declarativa.
- **Unicidad de nombres**: cerrada POR CONSTRUCCIÓN en el formato de origen
  (`mcpServers` es un objeto JSON keyed por nombre; un duplicado es imposible de
  representar). No es frontera abierta y por eso no hay regla.

Golden congelado: `examples/rules/mcp-golden.json`, sellado vía `golden: {path, sha256}`
en el rule-set y reproducido por el gate (`scripts/validate_rules.py`).
