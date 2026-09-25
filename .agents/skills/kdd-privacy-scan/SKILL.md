---
name: kdd-privacy-scan
description: Guia a cualquier agente (no depende de ningun modelo puntual) para producir un scan de datos personales/PII y su base legal de tratamiento en el formato de contrato de Capa 3 de KDD -- findings.json -- que despues gatea scripts/validate_privacy_findings.py. Usala cuando se pida mapear datos personales que recolecta un producto, auditar base legal de tratamiento, o se mencione "privacy scan", "PII", "data mapping" o "Capa 3" en el contexto de este template.
---

# Privacy Scan (Capa 3 de KDD -- PII / flujo de datos)

Produce hallazgos de datos personales y su base legal de tratamiento en el formato
de contrato que audita la Capa 3 de KDD. Esta skill NO es el gate -- es la parte
creativa/no determinista (mapear puntos de recoleccion, clasificar la categoria de
dato, juzgar si hay base legal declarada) que el gate despues valida. Distincion
central: **el agente decide QUE es un hallazgo de privacidad; el gate solo audita
que el artefacto sellado cumpla forma y politica de calidad de datos.**

Como [`kdd-compliance-scan`](../kdd-compliance-scan/SKILL.md), este dominio NO
vendoriza ningun sellador externo -- vos mismo escribis `findings.json` ya en forma
final, sin un finalizer aparte.

## Cuando usarla

El usuario pide mapear/auditar los datos personales que un repo/producto recolecta,
procesa o almacena, y quiere el resultado gobernado por KDD (versionable, gateado en
CI, con politica declarativa), no un reporte suelto en prosa.

## Insumos que necesitas antes de empezar

- `repo_root`: raiz del repositorio/producto a mapear.
- `scan_dir`: donde vas a escribir `findings.json`. Por defecto `privacy/scan`
  dentro del repo KDD (coincide con el default de
  `validate_privacy_findings.py`); si estas gobernando un repo EXTERNO, cualquier
  directorio disponible sirve, con tal de pasarselo explicito al gate.
- El schema completo vive en `knowledge/data_models/privacy/findings.schema.json`
  -- consultalo si dudas de un campo, no adivines la forma.

## Flujo

### 1. Mapea los puntos de recoleccion

Recorre el `repo_root` (formularios, endpoints de API, SDKs de terceros/analytics,
logs, colas de eventos) buscando donde entra un dato que identifica o puede
identificar a una persona: nombre, email, telefono, IP, identificadores de
dispositivo, datos financieros, de salud, biometricos, geolocalizacion, etc.

No inventes un finding para llenar un cupo: un mapeo que concluye "todo lo
recolectado tiene base legal declarada y categoria baja" es un resultado valido.

### 2. Clasifica cada dato

Por cada punto de recoleccion real, asigna `dataCategory`:

- `none` (dato que no identifica a una persona, aunque el punto de recoleccion
  parezca sensible a primera vista)
- `personal` (nombre, email, telefono, IP, identificador de cuenta/dispositivo)
- `sensitive-personal` (opinion politica, afiliacion sindical/religiosa,
  orientacion sexual -- "categorias especiales" en terminologia GDPR Art. 9)
- `financial` (numero de tarjeta, cuenta bancaria, historial de transacciones)
- `health` (datos de salud fisica o mental, diagnosticos, recetas)
- `biometric` (huella, reconocimiento facial, voz como identificador)

Verifica `legalBasis` -- lo que el producto DECLARA (en su politica de privacidad,
terminos, o el propio codigo si hay un flag de consentimiento) para justificar la
recoleccion:

- `consent` (el usuario opto explicitamente)
- `contract` (necesario para prestar el servicio pedido)
- `legitimate-interest` (interes legitimo del responsable, documentado)
- `legal-obligation` (una ley exige recolectarlo)
- `none-declared` (no encontraste ninguna base legal declarada -- tratalo como
  hallazgo de riesgo, no lo omitas)

`retentionDefined` (bool): si existe una politica de retencion/borrado declarada
para ese dato (TTL en la DB, job de purga, plazo en la politica de privacidad).

Para cada finding, junta ANTES de escribir el JSON:
- `collectionPoint` exacto (archivo:linea del formulario/endpoint, o nombre del
  SDK de terceros);
- `storageLocation` si lo sabes (tabla de DB, vendor de analytics, sink de logs);
- severidad honesta -- `none-declared` o categorias `sensitive-personal`/
  `health`/`biometric` normalmente son `high`/`critical`;
- una remediacion CONCRETA y accionable para cualquier `none-declared` o categoria
  sensible (no "revisar la politica de privacidad" -- eso no pasa el gate de
  politica, que exige remediaciones sustantivas de >=20 caracteres para esos casos).

### 3. Escribir el artefacto

En `<scan_dir>/findings.json`:

```json
{
  "documentType": "kdd-privacy.findings",
  "schemaVersion": "1.0",
  "scanId": "<identificador estable, p.ej. hash corto del commit + '_kdd-privacy-scan'>",
  "findings": [
    {
      "findingId": "priv_<collectionPoint-slug>-<secuencial>",
      "dataCategory": "...",
      "collectionPoint": "...",
      "storageLocation": "...",
      "legalBasis": "...",
      "retentionDefined": true,
      "severity": "...",
      "remediation": "...",
      "source": "manual review | static data-flow scan | DPIA excerpt | ..."
    }
  ]
}
```

`findingId` es responsabilidad tuya (no hay finalizer que lo derive): usa el punto
de recoleccion + un secuencial para que sea estable entre corridas del mismo scan.

### 4. Gatear

```
python scripts/validate_privacy_findings.py <scan_dir>
```

`FAIL` con violaciones reales (categoria/base legal fuera de enum, remediacion tipo
placeholder en un `none-declared` o categoria sensible, severidad insuficiente en un
`none-declared`) significa que el HALLAZGO esta mal capturado, no que el gate este
mal -- volve al paso 2 para ese finding especifico, no debilites la regla en
`examples/rules/privacy-findings.rules.json` para que pase.

### 5. Reportar

Devolve al usuario la ruta de `findings.json` y un resumen: cuantos puntos de
recoleccion se mapearon, cuantos findings de riesgo (`none-declared` o categorias
sensibles) se sellaron.

## Que NO hace esta skill

- No reemplaza un DPIA formal ni asesoria legal -- produce el artefacto gobernable
  que puede alimentar uno; la decision de que base legal usar o si se necesita
  consentimiento explicito sigue siendo humana/legal.
- No cubre mecanismos de transferencia internacional de datos (SCCs, decisiones de
  adecuacion, BCRs) ni el registro formal de actividades de tratamiento (RoPA) --
  esos viven fuera del artefacto sellado (ver el `code_only` de
  `privacy-findings.rules.json`).
- No escanea vulnerabilidades de seguridad ni licencias de dependencias -- esos son
  [`kdd-security-scan`](../kdd-security-scan/SKILL.md) y
  [`kdd-compliance-scan`](../kdd-compliance-scan/SKILL.md), dominios de politica
  distintos.
