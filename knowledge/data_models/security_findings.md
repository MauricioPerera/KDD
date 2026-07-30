---
type: 'Data Model'
title: 'Hallazgos de seguridad (Capa 3 de KDD)'
description: 'Modelo de datos del tercer dominio de KDD, junto a OKF (conocimiento) y CCDD (codigo): hallazgos de seguridad sellados en scan-manifest.json/findings.json/coverage.json (schemas vendorizados de openai/codex-security), gobernados por examples/rules/security-findings.rules.json via el mismo rule_engine.py declarativo de los demas dominios.'
tags: ['seguridad', 'security', 'rules', 'ccdd', 'vendor']
---

# Hallazgos de seguridad (Capa 3 de KDD)

Tercer dominio de KDD: gobierna hallazgos de seguridad de un repositorio con el mismo
motor declarativo (`rule_engine.py`) que ya gobierna registros MCP, pagos, fronteras,
etc. -- no se escribio codigo de motor nuevo para esta capa, solo un dominio de datos
y una policy.

## Procedencia (vendorizado, no reinventado)

El formato de artefacto y el sellador determinista se vendorizan sin reescribir desde
[openai/codex-security](https://github.com/openai/codex-security) (Apache-2.0),
verificado por ejecucion real (no solo lectura) en un entorno separado, sin el binario
`codex` ni ninguna API de OpenAI/GLM involucrada:

- **Schemas** (este directorio): `scan-manifest.schema.json`, `findings.schema.json`,
  `coverage.schema.json`.
- **Sellador**: `scripts/vendor/codex-security/finalize_scan_contract.py` (+ sus 3
  dependencias transitivas de carga dinamica -- ver
  `scripts/vendor/codex-security/README.md` para el arbol completo y por que el commit
  de origen esta pinneado ahi).

## Los 3 artefactos sellados

- `scan-manifest.json`: identidad del scan (`scan.id`, `producer`, `target`, `scope`),
  sellado con `sealedAt` + `artifacts[]` (sha256 de los otros dos) derivados por el
  finalizer, nunca escritos a mano.
- `findings.json`: array `findings[]`. Cada finding trae `findingId`/`occurrenceId`
  (derivados deterministicamente del `ruleId` + `identity.anchor` por el finalizer --
  el draft los deja en `"draft"`), `severity.level`, `confidence.level`,
  `taxonomy.cwe[]`, `locations[]`, `remediation`, `provenance.source`.
- `coverage.json`: que superficies se revisaron y su `disposition`
  (`reported`/`no_issue_found`/`rejected`/`not_applicable`/`needs_follow_up`).

## Record aplanado que consume la policy

`examples/rules/security-findings.rules.json` NO opera sobre el JSON Schema completo
(eso ya lo valido el finalizer al sellar) -- opera sobre un record aplanado que
`scripts/validate_security_findings.py` deriva de `findings.json`:

```json
{
  "findings": [
    {
      "findingId": "csf_...",
      "severityLevel": "critical",
      "confidenceLevel": "high",
      "cweCount": 1,
      "remediationLength": 87
    }
  ]
}
```

`cweCount` y `remediationLength` son campos CALCULADOS (no existen con ese nombre en
el `findings.json` sellado) precisamente para poder usar la familia `bounds` del rule
engine (que solo compara numeros) sobre propiedades de forma/calidad de texto que el
JSON Schema permite pero no exige (un `taxonomy.cwe: []` o una `remediation: "TBD"`
son schema-validos y policy-invalidos).

## Politica activa (examples/rules/security-findings.rules.json)

- Todo finding necesita >=1 CWE.
- Toda remediacion necesita >=20 caracteres (rechaza placeholders).
- Todo finding `severityLevel: critical` necesita `confidenceLevel: high` -- un
  hallazgo critico de confianza dudosa no se sella como si fuera definitivo; exige
  revision adicional antes de reportarse como tal.

## Frontera honesta (`code_only`)

El estado de triage (abierto / riesgo aceptado / corregido) vive en la base SQLite
del workbench de `codex-security`, NO en el `findings.json` sellado -- auditarlo
exige leer esa DB o un servidor MCP en vivo, fuera del alcance de un gate nivel 1
determinista y sin red. Documentado como entrada `code_only` en el rule-set, no
fingido como cubierto.

## Como se produce un finding (la parte no gateada)

Ver la skill [`kdd-security-scan`](../../.agents/skills/kdd-security-scan/SKILL.md):
gobierna el flujo de analisis (que hace un LLM, cualquiera, no atado a Codex) que
termina escribiendo el draft de estos 3 artefactos. Verificado con un agente
independiente (glm-5.2:cloud) que siguio la skill sin contexto previo y sello un
finding real al primer intento.
