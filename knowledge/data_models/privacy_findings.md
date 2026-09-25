---
type: 'Data Model'
title: 'Hallazgos de privacidad / PII (Capa 3 de KDD)'
description: 'Modelo de datos de un quinto dominio de KDD, junto a OKF (conocimiento), CCDD (codigo), hallazgos de seguridad y hallazgos de compliance/licencias: hallazgos de datos personales/flujo de datos en privacy/scan/findings.json, gobernados por examples/rules/privacy-findings.rules.json via el mismo rule_engine.py declarativo de los demas dominios.'
tags: ['privacidad', 'privacy', 'pii', 'rules', 'ccdd']
---

# Hallazgos de privacidad / PII (Capa 3 de KDD)

Dominio de KDD que gobierna hallazgos de datos personales y su base legal de
tratamiento, con el mismo motor declarativo (`rule_engine.py`) que ya gobierna
registros MCP, pagos, fronteras, seguridad y compliance de licencias -- no se
escribio codigo de motor nuevo para esta capa, solo un dominio de datos y una
policy.

## Sin vendoring (mismo criterio que compliance/licencias)

Como [compliance/licencias](./compliance_findings.md), este dominio NO
vendoriza ningun sellador externo: la identidad de un hallazgo de privacidad
(punto de recoleccion + categoria de dato) la decide quien produce el scan --
sea una revision manual, un escaner estatico de flujo de datos, o un extracto
de un DPIA (Data Protection Impact Assessment) ya existente -- no un
finalizer determinista como en seguridad. KDD normaliza y gatea, no
reimplementa deteccion de PII.

## El artefacto sellado

`privacy/scan/findings.json`: `documentType: "kdd-privacy.findings"` y
`findings[]`. Cada finding trae `findingId`, `dataCategory`
(`none`/`personal`/`sensitive-personal`/`financial`/`health`/`biometric`),
`collectionPoint` (donde se recolecta: campo de formulario, endpoint de API,
linea de log, SDK de terceros), `storageLocation` (donde se persiste, si se
conoce), `legalBasis`
(`consent`/`contract`/`legitimate-interest`/`legal-obligation`/`none-declared`),
`retentionDefined` (bool, si hay politica de retencion/borrado declarada),
`severity`, `remediation`, `source`. Schema completo:
`knowledge/data_models/privacy/findings.schema.json`.

## Record aplanado que consume la policy

`examples/rules/privacy-findings.rules.json` opera sobre un record aplanado
que `scripts/validate_privacy_findings.py` deriva de `findings.json`:

```json
{
  "findings": [
    {
      "findingId": "priv_signup-email-001",
      "dataCategory": "personal",
      "legalBasis": "consent",
      "severityLevel": "low",
      "remediationLength": 0
    }
  ]
}
```

`remediationLength` es un campo CALCULADO (no existe con ese nombre en el
`findings.json` sellado), mismo patron que security y compliance -- permite
usar la familia `bounds` del rule engine sobre la calidad del texto de
remediacion.

## Politica activa (examples/rules/privacy-findings.rules.json)

- Todo finding necesita `findingId`, `dataCategory`, `legalBasis` validos.
- `legalBasis: none-declared` exige `remediation` >=20 caracteres y severidad
  minima `high` -- un dato personal recolectado sin base legal declarada no
  se sella como si fuera un detalle menor.
- `dataCategory` en `sensitive-personal`/`health`/`biometric` exige
  `remediation` >=20 caracteres (rechaza placeholders) -- estas categorias
  son de mayor riesgo regulatorio (equivalentes a "categorias especiales" en
  GDPR Art. 9) y no se documentan con un "revisar despues".

## Frontera honesta (`code_only`)

Los mecanismos de transferencia internacional (Clausulas Contractuales
Tipo/SCCs, decisiones de adecuacion, Binding Corporate Rules) y el registro
formal de actividades de tratamiento (RoPA) viven fuera del `findings.json`
sellado -- auditarlos exige leer esos documentos legales/contractuales,
fuera del alcance de un gate nivel 1 determinista y sin red. Documentado como
entrada `code_only` en el rule-set, no fingido como cubierto.

## Como se produce un finding (la parte no gateada)

Ver la skill [`kdd-privacy-scan`](../../.agents/skills/kdd-privacy-scan/SKILL.md):
gobierna el flujo (mapear puntos de recoleccion de datos del repo/producto,
clasificar la categoria de dato, verificar si hay base legal y politica de
retencion declaradas) que termina escribiendo estos artefactos.
