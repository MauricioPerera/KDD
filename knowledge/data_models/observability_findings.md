---
type: 'Data Model'
title: 'Hallazgos de observabilidad (Capa 3 de KDD)'
description: 'Modelo de datos de un octavo dominio de KDD, junto a OKF (conocimiento), CCDD (codigo), hallazgos de seguridad, compliance/licencias, privacidad/PII, accesibilidad y vigencia de dependencias: hallazgos de gaps de logging/monitoreo/alertas en observability/scan/findings.json, gobernados por examples/rules/observability-findings.rules.json via el mismo rule_engine.py declarativo de los demas dominios.'
tags: ['observabilidad', 'observability', 'logging', 'rules', 'ccdd']
---

# Hallazgos de observabilidad (Capa 3 de KDD)

Dominio de KDD que gobierna hallazgos de gaps de observabilidad -- errores sin
loguear, fallos silenciosos, rutas criticas sin alertas ni tracing -- con el
mismo motor declarativo (`rule_engine.py`) que ya gobierna registros MCP,
pagos, fronteras, seguridad, compliance de licencias, privacidad,
accesibilidad y vigencia de dependencias -- no se escribio codigo de motor
nuevo para esta capa, solo un dominio de datos y una policy.

## Sin vendoring (mismo criterio que los demas dominios nativos)

Como los demas dominios nativos de KDD, este NO vendoriza ningun sellador
externo: la identidad de un gap de observabilidad (ubicacion + tipo de gap)
la decide quien revisa el codigo o los datos de produccion -- una revision
manual, un analisis estatico que busca bloques `except`/`catch` vacios, o el
post-mortem de un incidente real que revelo el gap. KDD normaliza esa
informacion al schema de este dominio y gatea, no reimplementa deteccion de
patrones de logging por ecosistema.

## El artefacto sellado

`observability/scan/findings.json`: `documentType:
"kdd-observability.findings"` y `findings[]`. Cada finding trae `findingId`,
`gapType`
(`unlogged-error-path`/`silent-failure`/`no-alerting`/`no-tracing`/`no-metrics`/`other`),
`location` (archivo:linea, servicio/endpoint, u operacion donde ocurre el
gap), `criticalPath` (bool, si la ubicacion esta en una ruta critica -- pago,
auth, riesgo de perdida de datos -- si se conoce), `severity`, `remediation`,
`source` (revision manual, analisis estatico, post-mortem de incidente).
Schema completo: `knowledge/data_models/observability/findings.schema.json`.

## Record aplanado que consume la policy

`examples/rules/observability-findings.rules.json` opera sobre un record
aplanado que `scripts/validate_observability_findings.py` deriva de
`findings.json`:

```json
{
  "findings": [
    {
      "findingId": "obs_checkout-catch-001",
      "gapType": "silent-failure",
      "severityLevel": "high",
      "remediationLength": 0
    }
  ]
}
```

`remediationLength` es un campo CALCULADO (no existe con ese nombre en el
`findings.json` sellado), mismo patron que los demas dominios -- permite usar
la familia `bounds` del rule engine sobre la calidad del texto de
remediacion.

## Politica activa (examples/rules/observability-findings.rules.json)

- Todo finding necesita `findingId`, `gapType`, `severity` validos.
- `severity` en `critical`/`high` exige `remediation` >=20 caracteres
  (rechaza placeholders) -- un gap de observabilidad de impacto alto no se
  documenta con un "agregar logging despues": significa que, hoy, un fallo en
  esa ruta pasa desapercibido.

## Frontera honesta (`code_only`)

Verificar que una alerta configurada REALMENTE dispara (no solo que la regla
existe en el sistema de monitoreo) exige simular el incidente en un entorno
real o esperar el proximo incidente real -- fuera del alcance de un gate
nivel 1 determinista y sin red. Documentado como entrada `code_only` en el
rule-set, no fingido como cubierto.

## Como se produce un finding (la parte no gateada)

Ver la skill
[`kdd-observability-scan`](../../.agents/skills/kdd-observability-scan/SKILL.md):
gobierna el flujo (identificar rutas criticas del sistema, revisar manejo de
errores y cobertura de alertas/tracing en esas rutas, normalizar al schema de
este dominio) que termina escribiendo estos artefactos.
