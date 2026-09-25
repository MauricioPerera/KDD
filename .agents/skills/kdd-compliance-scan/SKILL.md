---
name: kdd-compliance-scan
description: Guia a cualquier agente (no depende de ningun modelo puntual) para producir un scan de compatibilidad de licencias de dependencias de un repositorio en el formato de contrato de Capa 3 de KDD -- findings.json -- que despues gatea scripts/validate_compliance_findings.py. Usala cuando se pida auditar licencias de dependencias, verificar compliance de un package.json/requirements.txt/Cargo.toml/go.mod, o se mencione "license scan", "compliance findings" o "Capa 3" en el contexto de este template.
---

# Compliance Scan (Capa 3 de KDD -- licencias)

Produce hallazgos de compatibilidad de licencias de dependencias en el formato de
contrato que audita la Capa 3 de KDD. Esta skill NO es el gate -- es la parte
creativa/no determinista (normalizar la salida de un scanner de licencias a un
juicio de compatibilidad) que el gate despues valida. Distincion central: **el
agente/scanner decide la categoria y compatibilidad de cada licencia; el gate solo
audita que el artefacto sellado cumpla forma y politica de calidad de datos.**

A diferencia de [`kdd-security-scan`](../kdd-security-scan/SKILL.md), este dominio
NO vendoriza ningun sellador externo: la identidad de un finding (nombre+version de
dependencia) ya la resuelve de forma estable la herramienta de licencias del
ecosistema del repo, asi que no hace falta un finalizer aparte -- vos mismo escribis
`findings.json` ya en forma final.

## Cuando usarla

El usuario pide auditar las licencias de las dependencias de un repo (propio o
externo) y quiere el resultado gobernado por KDD (versionable, gateado en CI, con
politica declarativa), no un reporte suelto en prosa.

## Insumos que necesitas antes de empezar

- `repo_root`: raiz del repositorio a escanear.
- `project_license`: identificador SPDX de la licencia del propio proyecto (leelo de
  `LICENSE`/`package.json`/`Cargo.toml`/etc. -- si no esta declarada, decilo
  explicito en el reporte en vez de adivinar).
- `scan_dir`: donde vas a escribir `findings.json`. Por defecto `compliance/scan`
  dentro del repo KDD (coincide con el default de
  `validate_compliance_findings.py`); si estas gobernando un repo EXTERNO, cualquier
  directorio disponible sirve, con tal de pasarselo explicito al gate.
- El schema completo vive en `knowledge/data_models/compliance/findings.schema.json`
  -- consultalo si dudas de un campo, no adivines la forma.

## Flujo

### 1. Elegi el scanner del ecosistema

No reimplementes deteccion de licencias: corre la herramienta estandar del
ecosistema del repo y consumi su salida JSON.

| Ecosistema | Herramienta | Comando tipico |
|---|---|---|
| Python | `pip-licenses` | `pip-licenses --format=json --with-urls` |
| Node/TS | `license-checker` | `npx license-checker --json` |
| Rust | `cargo-license` | `cargo license --json` |
| Go | `go-licenses` | `go-licenses report ./...` |

Si el repo mezcla ecosistemas, corre una herramienta por cada uno y juntalos en un
solo `findings.json`.

### 2. Clasifica cada licencia

Por cada dependencia que reporte el scanner, asigna `licenseCategory`:

- `permissive` (MIT, BSD-*, Apache-2.0, ISC, ...)
- `weak-copyleft` (LGPL-*, MPL-2.0, ...)
- `strong-copyleft` (GPL-*, AGPL-*, ...)
- `proprietary` (licencia comercial/cerrada declarada)
- `unknown` (el scanner no pudo determinarla, o el paquete no declara ninguna)

Decidi `compatibleWithProjectLicense` comparando contra `project_license` (juicio de
dominio, no mecanizable declarativamente por el rule engine -- por eso lo decide
quien produce el scan, no el gate). Como guia rapida: `strong-copyleft` casi nunca es
compatible con un `project_license` permissive si la dependencia se enlaza/distribuye
(no si es solo una devDependency de build); `unknown` nunca se declara compatible por
default -- tratalo como riesgo hasta identificarlo.

No inventes un finding para llenar un cupo: un scan con solo dependencias
`permissive` compatibles y cero findings de riesgo es un resultado valido.

Para cada finding, junta ANTES de escribir el JSON:
- `dependencyName`/`dependencyVersion` exactos (los que reporto el scanner);
- `license` (SPDX, o `"unknown"` si el scanner no la determino);
- severidad honesta -- `unknown`/`strong-copyleft` incompatible normalmente es
  `high`; `weak-copyleft` compatible puede ser `low`/`informational`;
- una remediacion CONCRETA y accionable para cualquier `strong-copyleft` o
  `unknown` (no "revisar la licencia" -- eso no pasa el gate de politica, que exige
  remediaciones sustantivas de >=20 caracteres para esos dos casos).

### 3. Escribir el artefacto

En `<scan_dir>/findings.json`:

```json
{
  "documentType": "kdd-compliance.findings",
  "schemaVersion": "1.0",
  "scanId": "<identificador estable, p.ej. hash corto del commit + '_kdd-compliance-scan'>",
  "projectLicense": "<SPDX del proyecto>",
  "findings": [
    {
      "findingId": "lic_<dependencyName>-<dependencyVersion>",
      "dependencyName": "...",
      "dependencyVersion": "...",
      "license": "...",
      "licenseCategory": "...",
      "compatibleWithProjectLicense": true,
      "severity": "...",
      "remediation": "...",
      "source": "pip-licenses | license-checker | cargo-license | go-licenses | ..."
    }
  ]
}
```

`findingId` es responsabilidad tuya (no hay finalizer que lo derive): usa
`dependencyName`+`dependencyVersion` para que sea estable entre corridas del mismo
scan.

### 4. Gatear

```
python scripts/validate_compliance_findings.py <scan_dir>
```

`FAIL` con violaciones reales (categoria fuera de enum, remediacion tipo placeholder
en un `strong-copyleft`/`unknown`, severidad insuficiente en un `unknown`) significa
que el HALLAZGO esta mal capturado, no que el gate este mal -- volve al paso 2 para
ese finding especifico, no debilites la regla en
`examples/rules/compliance-findings.rules.json` para que pase.

### 5. Reportar

Devolve al usuario la ruta de `findings.json` y un resumen: cuantas dependencias se
revisaron, cuantos findings de riesgo (`strong-copyleft`/`unknown`/incompatibles) se
sellaron, y el `project_license` usado como referencia.

## Que NO hace esta skill

- No decide automaticamente que hacer ante una incompatibilidad real (reemplazar la
  dependencia, negociar una excepcion comercial, aceptar el riesgo) -- produce el
  artefacto gobernable; la decision sigue siendo humana. Excepciones comerciales
  firmadas fuera del repo viven fuera del artefacto sellado (ver el `code_only` de
  `compliance-findings.rules.json`).
- No escanea vulnerabilidades de seguridad en las dependencias -- eso es
  [`kdd-security-scan`](../kdd-security-scan/SKILL.md), un dominio de politica
  distinto.
