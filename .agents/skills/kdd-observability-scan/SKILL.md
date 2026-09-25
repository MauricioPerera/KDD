---
name: kdd-observability-scan
description: Guia a cualquier agente (no depende de ningun modelo puntual) para producir un scan de gaps de observabilidad (logging/alertas/tracing/metricas faltantes en rutas criticas) en el formato de contrato de Capa 3 de KDD -- findings.json -- que despues gatea scripts/validate_observability_findings.py. Usala cuando se pida auditar cobertura de logging/monitoreo, revisar manejo de errores en rutas criticas, o se mencione "observability", "logging gaps", "silent failures" o "Capa 3" en el contexto de este template.
---

# Observability Scan (Capa 3 de KDD -- gaps de logging/monitoreo)

Produce hallazgos de gaps de observabilidad en el formato de contrato que
audita la Capa 3 de KDD. Esta skill NO es el gate -- es la parte
creativa/no determinista (identificar rutas criticas, revisar su manejo de
errores y cobertura de alertas/tracing, juzgar el impacto de cada gap) que
el gate despues valida. Distincion central: **el agente decide QUE es un
gap de observabilidad; el gate solo audita que el artefacto sellado cumpla
forma y politica de calidad de datos.**

Como los demas dominios nativos de KDD (`kdd-compliance-scan`,
`kdd-privacy-scan`, `kdd-accessibility-scan`, `kdd-dependency-eol-scan`),
esta skill NO vendoriza ningun sellador externo -- vos mismo escribis
`findings.json` ya en forma final.

## Cuando usarla

El usuario pide auditar si los errores de un sistema se detectan a tiempo
(logueados, alertados, trazables) y quiere el resultado gobernado por KDD
(versionable, gateado en CI, con politica declarativa), no un reporte
suelto en prosa.

## Insumos que necesitas antes de empezar

- `repo_root`: raiz del repositorio/producto a revisar.
- `scan_dir`: donde vas a escribir `findings.json`. Por defecto
  `observability/scan` dentro del repo KDD (coincide con el default de
  `validate_observability_findings.py`); si estas gobernando un repo
  EXTERNO, cualquier directorio disponible sirve, con tal de pasarselo
  explicito al gate.
- El schema completo vive en
  `knowledge/data_models/observability/findings.schema.json` -- consultalo
  si dudas de un campo, no adivines la forma.

## Flujo

### 1. Identifica las rutas criticas

Antes de revisar codigo, fija por escrito (2-3 lineas) que operaciones son
criticas para este sistema: las que mueven dinero, autentican usuarios,
escriben datos irreversibles, o cuyo fallo silencioso tendria el mayor
costo de deteccion tardia. Esto acota donde buscar -- no hace falta
revisar cada linea del repo, si el sistema entero.

### 2. Revisa manejo de errores en esas rutas

Busca patrones concretos, no impresiones generales:

- bloques `try`/`except`/`catch` que capturan la excepcion y NO la loguean
  ni la re-lanzan (`except: pass` o equivalente -- el patron mas peligroso,
  `silent-failure`);
- rutas de error que loguean pero sin contexto suficiente para diagnosticar
  (`unlogged-error-path` si el log directamente no existe);
- operaciones criticas sin ninguna alerta configurada que dispare ante un
  fallo (`no-alerting`);
- llamadas entre servicios sin ID de correlacion/trace propagado, que
  impide reconstruir un flujo cuando algo falla (`no-tracing`);
- operaciones criticas sin ningun contador/metrica que permita detectar
  degradacion antes de que se vuelva un incidente (`no-metrics`).

No inventes un finding para llenar un cupo: rutas criticas bien
instrumentadas es un resultado valido, mismo criterio que los demas
dominios de esta familia.

Para cada gap real, junta ANTES de escribir el JSON:
- `location` exacta (archivo:linea, nombre del servicio/endpoint, o la
  operacion concreta);
- si la ubicacion es realmente una ruta critica (`criticalPath: true`) o
  una zona de menor impacto;
- severidad honesta -- un `silent-failure` en una ruta de pago es
  `critical`; un `no-metrics` en un endpoint de baja frecuencia puede ser
  `low`;
- una remediacion CONCRETA y accionable para cualquier finding
  `critical`/`high` (no "mejorar el logging" a secas -- nombra que agregar
  y donde; eso no pasa el gate de politica, que exige remediaciones
  sustantivas de >=20 caracteres para esos dos niveles).

### 3. Escribir el artefacto

En `<scan_dir>/findings.json`:

```json
{
  "documentType": "kdd-observability.findings",
  "schemaVersion": "1.0",
  "scanId": "<identificador estable, p.ej. hash corto del commit + '_kdd-observability-scan'>",
  "findings": [
    {
      "findingId": "obs_<ubicacion-slug>-<secuencial>",
      "gapType": "silent-failure",
      "location": "...",
      "criticalPath": true,
      "severity": "...",
      "remediation": "...",
      "source": "manual review | static analysis | incident postmortem"
    }
  ]
}
```

`findingId` es responsabilidad tuya (no hay finalizer que lo derive): usa
la ubicacion + un secuencial para que sea estable entre corridas del mismo
scan.

### 4. Gatear

```
python scripts/validate_observability_findings.py <scan_dir>
```

`FAIL` con violaciones reales (`gapType`/`severity` fuera de enum,
remediacion tipo placeholder en un `critical`/`high`) significa que el
HALLAZGO esta mal capturado, no que el gate este mal -- volve al paso 2
para ese finding especifico, no debilites la regla en
`examples/rules/observability-findings.rules.json` para que pase.

### 5. Reportar

Devolve al usuario la ruta de `findings.json` y un resumen: que rutas
criticas se revisaron, cuantos findings `critical`/`high` se sellaron.

## Que NO hace esta skill

- No verifica que una alerta configurada REALMENTE dispare ante un
  incidente real -- eso exige simular el incidente o esperar el proximo,
  fuera del artefacto sellado (ver el `code_only` de
  `observability-findings.rules.json`).
- No reemplaza un post-mortem formal de un incidente ya ocurrido -- puede
  alimentarse de uno (`source: "incident postmortem"`), pero la skill en si
  es preventiva, no de respuesta a incidentes.
- No audita seguridad, licencias, privacidad ni accesibilidad -- esos son
  otros dominios de esta misma familia (`kdd-security-scan`,
  `kdd-compliance-scan`, `kdd-privacy-scan`, `kdd-accessibility-scan`).
