---
type: 'Data Model'
title: 'Cableado de agentes (agente-skills-MCP)'
description: 'La composición de un agente como contrato: qué skills usa, qué servidores MCP, con qué modelo y qué política de re-delegación. Reglas declarativas para la forma; integridad referencial cerrada por código (check_agent_wiring). Las 3 capas honestas de "contratar un agente".'
tags: ['agentes', 'wiring', 'rules', 'example']
---

# Cableado de agentes (dominio de ejemplo)

Respuesta a "¿puedo tener un contrato para un agente?" — en TRES capas honestas:

1. **Definiciones del agente** (archivos tipo `.claude/agents/*.md`): contratable con un
   gate estilo skills (C24) — pero el RECON del Contrato 26 encontró CERO definiciones
   reales en el entorno. Por doctrina evidencia-primero ese gate NO se construye
   especulativamente; queda anotado aquí para cuando el activo exista.
2. **El cableado** (este dominio): qué agente usa qué skills, qué servidores MCP, con qué
   modelo y qué política de re-delegación. Datos sintéticos modelados sobre el flujo real
   de la metodología (PM nativo + devs efímeros haiku, máximo 2 re-delegaciones).
3. **El comportamiento del agente**: NO contratable determinísticamente — y esa es la
   tesis de CCDD: no se contrata al agente, se contrata el ARTEFACTO que produce (oráculo
   congelado + gates). La capa 3 no es una frontera pendiente; es el fundamento.

## Formato del record (forma auditoría, plano)

```json
{
  "agents": [{"name": "pm-nativo", "model": "fable", "max_redelegations": 2}],
  "skills_registry": ["pm-native-ccdd", "delegar-glm-ccdd"],
  "mcp_registry": ["ccdd-complexity", "pocketbase"],
  "agent_skills": [{"agent": "pm-nativo", "skill": "pm-native-ccdd"}],
  "agent_mcp": [{"agent": "pm-nativo", "server": "ccdd-complexity"}]
}
```

## Reglas declarativas (examples/rules/agent-wiring.rules.json)

- `agents` presente.
- `each agents`: `name` y `model` presentes; `name` kebab-case (`matches`); `model` en
  `{haiku, sonnet, opus, fable}`; `max_redelegations` number con bounds [0, 2] — la
  política real de re-delegación de la metodología, como dato.
- `each agent_skills`: `agent` y `skill` presentes.
- `each agent_mcp`: `agent` y `server` presentes.

## Frontera medida: integridad referencial bajo cuantificación

"La skill referenciada debe EXISTIR en `skills_registry`" es una referencia CRUZADA entre
colecciones dentro de `each`. La familia `refs` opera sobre campos top-level del record,
no sobre elementos de una lista: `refs`-dentro-de-`each` sería una familia nueva y esta es
su PRIMERA aparición ⇒ no se agrega familia (evidencia-primero). La frontera queda
`code_only` en el rule-set y se cierra por código — [check_agent_wiring](../contracts/check-agent-wiring.md),
precedente C22 — encadenando de facto este dominio con los gates de skills (C24) y del
registro MCP (C25): agente → skills existentes → servidores registrados.

Golden congelado: `examples/rules/agent-wiring-golden.json` (el caso FRONTERA ejercita
`code_only_miss` y el checker lo atrapa — verificado por cross-check en el cierre).
