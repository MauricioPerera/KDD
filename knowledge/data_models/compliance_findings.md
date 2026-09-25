---
type: 'Data Model'
title: 'Hallazgos de licencias/compliance (Capa 3 de KDD)'
description: 'Modelo de datos de un cuarto dominio de KDD, junto a OKF (conocimiento), CCDD (codigo) y hallazgos de seguridad: hallazgos de compatibilidad de licencias de dependencias en compliance/scan/findings.json, gobernados por examples/rules/compliance-findings.rules.json via el mismo rule_engine.py declarativo de los demas dominios.'
tags: ['compliance', 'licencias', 'rules', 'ccdd']
---

# Hallazgos de licencias/compliance (Capa 3 de KDD)

Dominio de KDD que gobierna hallazgos de compatibilidad de licencias de dependencias
con el mismo motor declarativo (`rule_engine.py`) que ya gobierna registros MCP,
pagos, fronteras, seguridad, etc. -- no se escribio codigo de motor nuevo para esta
capa, solo un dominio de datos y una policy.

## Sin vendoring (a diferencia de seguridad)

El dominio de seguridad (`knowledge/data_models/security_findings.md`) vendoriza un
sellador de [openai/codex-security](https://github.com/openai/codex-security) porque
escanea codigo propio del repo objetivo. Compliance de licencias no necesita eso: la
identidad de un hallazgo (nombre+version de dependencia) ya la resuelven determinista
y establemente herramientas estandar por ecosistema (`pip-licenses`, `license-checker`,
`cargo-license`, `go-licenses`, entre otras) -- KDD solo necesita normalizar su salida
al schema de este dominio y gatear la calidad de los datos, sin reimplementar ni
vendorizar ningun scanner.

## El artefacto sellado

`compliance/scan/findings.json`: `documentType: "kdd-compliance.findings"`,
`projectLicense` (SPDX del propio proyecto, referencia para decidir compatibilidad) y
`findings[]`. Cada finding trae `findingId`, `dependencyName`/`dependencyVersion`,
`license` (SPDX o `"unknown"`), `licenseCategory`
(`permissive`/`weak-copyleft`/`strong-copyleft`/`proprietary`/`unknown`),
`compatibleWithProjectLicense` (bool, decidido por quien normaliza la salida del
scanner contra `projectLicense` -- NO por el rule gate, que solo audita forma/calidad),
`severity`, `remediation`, `source` (que herramienta lo produjo). Schema completo:
`knowledge/data_models/compliance/findings.schema.json`.

## Record aplanado que consume la policy

`examples/rules/compliance-findings.rules.json` opera sobre un record aplanado que
`scripts/validate_compliance_findings.py` deriva de `findings.json`:

```json
{
  "findings": [
    {
      "findingId": "lic_left-pad-1.3.0",
      "licenseCategory": "permissive",
      "severityLevel": "informational",
      "remediationLength": 0
    }
  ]
}
```

`remediationLength` es un campo CALCULADO (no existe con ese nombre en el
`findings.json` sellado), igual que en el dominio de seguridad -- permite usar la
familia `bounds` del rule engine sobre la calidad del texto de remediacion.

## Politica activa (examples/rules/compliance-findings.rules.json)

- Todo finding necesita `findingId`, `dependencyName`, `licenseCategory` validos.
- `licenseCategory: strong-copyleft` o `unknown` exige `remediation` >=20 caracteres
  (rechaza placeholders -- una licencia fuerte o no identificada no se sella sin
  explicar que se hizo al respecto).
- `licenseCategory: unknown` exige severidad minima `high` -- no se puede ignorar en
  silencio una dependencia con licencia no identificada.

## Frontera honesta (`code_only`)

Si una dependencia declara excepciones de licencia dual o acuerdos comerciales
puntuales (p.ej. un `commercial-license.pdf` firmado fuera del repo), eso vive fuera
del `findings.json` sellado -- auditarlo exige leer ese documento externo, fuera del
alcance de un gate nivel 1 determinista y sin red. Documentado como entrada
`code_only` en el rule-set, no fingido como cubierto.

## Como se produce un finding (la parte no gateada)

Ver la skill [`kdd-compliance-scan`](../../.agents/skills/kdd-compliance-scan/SKILL.md):
gobierna el flujo (correr el scanner de licencias del ecosistema del repo, normalizar
su salida al schema de este dominio, decidir `compatibleWithProjectLicense` contra
`projectLicense`) que termina escribiendo estos artefactos.
