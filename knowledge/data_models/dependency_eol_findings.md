---
type: 'Data Model'
title: 'Hallazgos de vigencia de dependencias / EOL (Capa 3 de KDD)'
description: 'Modelo de datos de un septimo dominio de KDD, junto a OKF (conocimiento), CCDD (codigo), hallazgos de seguridad, compliance/licencias, privacidad/PII y accesibilidad: hallazgos de dependencias desactualizadas/sin mantenimiento/fuera de soporte en dependency-eol/scan/findings.json, gobernados por examples/rules/dependency-eol-findings.rules.json via el mismo rule_engine.py declarativo de los demas dominios.'
tags: ['dependencias', 'eol', 'mantenimiento', 'rules', 'ccdd']
---

# Hallazgos de vigencia de dependencias / EOL (Capa 3 de KDD)

Dominio de KDD que gobierna hallazgos sobre la salud de mantenimiento de las
dependencias de un proyecto -- versiones desactualizadas, paquetes fuera de
soporte (End-Of-Life) o abandonados por su autor -- con el mismo motor
declarativo (`rule_engine.py`) que ya gobierna registros MCP, pagos, fronteras,
seguridad, compliance de licencias, privacidad y accesibilidad -- no se escribio
codigo de motor nuevo para esta capa, solo un dominio de datos y una policy.

## No es lo mismo que compliance/licencias

[Compliance/licencias](./compliance_findings.md) audita si la LICENCIA de una
dependencia es compatible con la del proyecto. Este dominio audita si la
dependencia sigue VIGENTE (mantenida, soportada, con parches de seguridad
disponibles) independientemente de su licencia -- una dependencia MIT puede
estar perfectamente bien licenciada y a la vez llevar 3 anios sin un commit o
tener su fecha de EOL declarada ya pasada. Son ejes de riesgo distintos; un
proyecto puede usar los dos dominios a la vez sin conflicto.

## Sin vendoring (mismo criterio que compliance/privacidad/accesibilidad)

Como los demas dominios nativos de KDD, este NO vendoriza ningun sellador
externo: la vigencia de una dependencia la resuelven fuentes estandar
(endoflife.date, `npm outdated`, `pip list --outdated`, `cargo outdated`,
`go list -u -m all`, el registro de paquetes del ecosistema) -- no un
finalizer determinista propio de KDD. KDD normaliza esa informacion al schema
de este dominio y gatea, no reimplementa el rastreo de fechas de EOL de cada
ecosistema.

## El artefacto sellado

`dependency-eol/scan/findings.json`: `documentType:
"kdd-dependency-eol.findings"` y `findings[]`. Cada finding trae `findingId`,
`dependencyName`/`dependencyVersion`, `latestVersion` (si se conoce),
`eolStatus` (`supported`/`approaching-eol`/`eol`/`unmaintained`/`unknown`),
`eolDate` (fecha declarada por el publisher, si se conoce), `severity`,
`remediation`, `source` (que fuente/herramienta lo produjo). Schema completo:
`knowledge/data_models/dependency-eol/findings.schema.json`.

`eolStatus: unmaintained` es distinto de `eolStatus: eol`: `eol` exige una
fecha de fin de vida/soporte DECLARADA por el publisher que ya paso;
`unmaintained` cubre el caso -- mas comun y mas dificil de detectar
automaticamente -- de un paquete sin fecha de EOL formal pero sin actividad
real del mantenedor en mucho tiempo (repositorio abandonado).

## Record aplanado que consume la policy

`examples/rules/dependency-eol-findings.rules.json` opera sobre un record
aplanado que `scripts/validate_dependency_eol_findings.py` deriva de
`findings.json`:

```json
{
  "findings": [
    {
      "findingId": "eol_leftpad-1.3.0",
      "eolStatus": "supported",
      "severityLevel": "informational",
      "remediationLength": 0
    }
  ]
}
```

`remediationLength` es un campo CALCULADO (no existe con ese nombre en el
`findings.json` sellado), mismo patron que los demas dominios -- permite usar
la familia `bounds` del rule engine sobre la calidad del texto de
remediacion.

## Politica activa (examples/rules/dependency-eol-findings.rules.json)

- Todo finding necesita `findingId`, `dependencyName`, `eolStatus` validos.
- `eolStatus` en `eol`/`unmaintained` exige `remediation` >=20 caracteres
  (rechaza placeholders) y severidad minima `high` -- una dependencia sin
  soporte activo no se documenta con un "actualizar despues": expone al
  proyecto a vulnerabilidades sin parche disponible.

## Frontera honesta (`code_only`)

La evaluacion de riesgo real de mantener una dependencia EOL a proposito
(p.ej. un fork interno mantenido por el propio equipo, o un acuerdo de
soporte extendido pagado con el vendor) vive fuera del `findings.json`
sellado -- verificar esos acuerdos exige leer documentos contractuales
externos, fuera del alcance de un gate nivel 1 determinista y sin red.
Documentado como entrada `code_only` en el rule-set, no fingido como
cubierto.

## Como se produce un finding (la parte no gateada)

Ver la skill
[`kdd-dependency-eol-scan`](../../.agents/skills/kdd-dependency-eol-scan/SKILL.md):
gobierna el flujo (listar dependencias directas del proyecto, consultar su
estado de vigencia via las fuentes del ecosistema, normalizar al schema de
este dominio) que termina escribiendo estos artefactos.
