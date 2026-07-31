---
name: kdd-dependency-eol-scan
description: Guia a cualquier agente (no depende de ningun modelo puntual) para producir un scan de vigencia de dependencias (End-Of-Life / abandono de mantenimiento) en el formato de contrato de Capa 3 de KDD -- findings.json -- que despues gatea scripts/validate_dependency_eol_findings.py. Usala cuando se pida auditar si las dependencias de un proyecto siguen soportadas, correr endoflife.date/npm outdated/pip list --outdated, o se mencione "EOL", "end of life", "dependencias desactualizadas" o "Capa 3" en el contexto de este template. NO confundir con kdd-compliance-scan (audita LICENCIA, no vigencia).
---

# Dependency EOL Scan (Capa 3 de KDD -- vigencia de dependencias)

Produce hallazgos de vigencia de dependencias (fuera de soporte, abandonadas, o
proximas a su fecha de fin de vida) en el formato de contrato que audita la
Capa 3 de KDD. Esta skill NO es el gate -- es la parte creativa/no determinista
(consultar el estado de vigencia real de cada dependencia y decidir su
`eolStatus`) que el gate despues valida. Distincion central: **el
scanner/agente decide el estado de vigencia; el gate solo audita que el
artefacto sellado cumpla forma y politica de calidad de datos.**

Como [`kdd-compliance-scan`](../kdd-compliance-scan/SKILL.md) y
[`kdd-privacy-scan`](../kdd-privacy-scan/SKILL.md), este dominio NO vendoriza
ningun sellador externo -- vos mismo escribis `findings.json` ya en forma
final.

## No es lo mismo que `kdd-compliance-scan`

[`kdd-compliance-scan`](../kdd-compliance-scan/SKILL.md) audita si la LICENCIA
de una dependencia es compatible con la del proyecto. Esta skill audita si la
dependencia sigue VIGENTE (mantenida, con soporte activo) independientemente
de su licencia. Una dependencia puede estar perfectamente licenciada (MIT) y a
la vez estar sin mantenimiento hace anios. Corre las dos skills si queres
cobertura completa de riesgo de dependencias -- son hallazgos independientes,
en dominios (y `findings.json`) separados.

## Cuando usarla

El usuario pide auditar si las dependencias directas de un proyecto siguen
soportadas/mantenidas, y quiere el resultado gobernado por KDD (versionable,
gateado en CI, con politica declarativa), no un reporte suelto en prosa.

## Insumos que necesitas antes de empezar

- `repo_root`: raiz del repositorio a escanear.
- `scan_dir`: donde vas a escribir `findings.json`. Por defecto
  `dependency-eol/scan` dentro del repo KDD (coincide con el default de
  `validate_dependency_eol_findings.py`); si estas gobernando un repo
  EXTERNO, cualquier directorio disponible sirve, con tal de pasarselo
  explicito al gate.
- El schema completo vive en
  `knowledge/data_models/dependency-eol/findings.schema.json` -- consultalo
  si dudas de un campo, no adivines la forma.

## Flujo

### 1. Lista las dependencias directas

Lee el manifiesto del ecosistema del repo (`package.json`,
`requirements.txt`/`pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, etc.)
y queda con la lista de dependencias DIRECTAS (no transitivas -- el volumen de
transitivas suele ser enorme y el riesgo real esta en lo que el proyecto
declara explicitamente).

### 2. Consulta el estado de vigencia de cada una

No reimplementes rastreo de fechas de EOL: usa fuentes estandar.

| Fuente | Cubre | Uso tipico |
|---|---|---|
| [endoflife.date](https://endoflife.date) API | Runtimes, frameworks, DBs con ciclo de vida formal declarado | `GET https://endoflife.date/api/<producto>.json` |
| `npm outdated` / `npm view <pkg> time` | Paquetes npm, fecha del ultimo publish | CLI |
| `pip list --outdated` / PyPI API | Paquetes Python | CLI / `https://pypi.org/pypi/<pkg>/json` |
| `cargo outdated` | Crates de Rust | CLI (requiere `cargo-outdated`) |
| `go list -u -m all` | Modulos Go | CLI |
| Revision manual del repo upstream | Cualquier ecosistema, cuando no hay fecha de EOL formal | Ultimo commit/release en GitHub/GitLab del paquete |

Para cada dependencia, decidi `eolStatus`:

- `supported`: version reciente, mantenedor activo, sin fecha de EOL cercana.
- `approaching-eol`: el publisher declaro una fecha de fin de soporte que
  esta a menos de ~6 meses (ajusta segun el contexto del proyecto).
- `eol`: la fecha de fin de vida/soporte DECLARADA por el publisher ya paso.
- `unmaintained`: SIN fecha de EOL formal, pero sin actividad real (commits,
  releases, respuestas a issues) en mucho tiempo -- juicio del agente, no
  mecanizable de forma universal.
- `unknown`: no encontraste informacion confiable -- no lo declares
  `supported` por default, eso oculta el riesgo.

No inventes un finding para llenar un cupo: un scan donde todo esta
`supported` es un resultado valido.

Para cada finding `eol`/`unmaintained`, junta ANTES de escribir el JSON:
- `dependencyName`/`dependencyVersion` exactos, `latestVersion` si la
  encontraste;
- `eolDate` si el publisher la declaro formalmente;
- severidad honesta -- `eol`/`unmaintained` normalmente son `high`/`critical`
  (mas alto si la dependencia maneja datos sensibles o esta expuesta a red);
- una remediacion CONCRETA y accionable (no "actualizar la dependencia" a
  secas -- nombra la alternativa concreta si la conoces, o el plan de
  migracion; eso no pasa el gate de politica, que exige remediaciones
  sustantivas de >=20 caracteres para `eol`/`unmaintained`).

### 3. Escribir el artefacto

En `<scan_dir>/findings.json`:

```json
{
  "documentType": "kdd-dependency-eol.findings",
  "schemaVersion": "1.0",
  "scanId": "<identificador estable, p.ej. hash corto del commit + '_kdd-dependency-eol-scan'>",
  "findings": [
    {
      "findingId": "eol_<dependencyName>-<dependencyVersion>",
      "dependencyName": "...",
      "dependencyVersion": "...",
      "latestVersion": "...",
      "eolStatus": "...",
      "eolDate": "...",
      "severity": "...",
      "remediation": "...",
      "source": "endoflife.date | npm outdated | pip list --outdated | manual review | ..."
    }
  ]
}
```

`findingId` es responsabilidad tuya (no hay finalizer que lo derive): usa
`dependencyName`+`dependencyVersion` para que sea estable entre corridas del
mismo scan.

### 4. Gatear

```
python scripts/validate_dependency_eol_findings.py <scan_dir>
```

`FAIL` con violaciones reales (estado fuera de enum, remediacion tipo
placeholder en un `eol`/`unmaintained`, severidad insuficiente) significa que
el HALLAZGO esta mal capturado, no que el gate este mal -- volve al paso 2
para ese finding especifico, no debilites la regla en
`examples/rules/dependency-eol-findings.rules.json` para que pase.

### 5. Reportar

Devolve al usuario la ruta de `findings.json` y un resumen: cuantas
dependencias directas se revisaron, cuantos findings `eol`/`unmaintained` se
sellaron.

## Que NO hace esta skill

- No decide automaticamente la migracion (reemplazar la dependencia, hacer un
  fork interno, negociar soporte extendido pagado) -- produce el artefacto
  gobernable; la decision sigue siendo humana. Acuerdos de soporte extendido
  documentados viven fuera del artefacto sellado (ver el `code_only` de
  `dependency-eol-findings.rules.json`).
- No audita licencias ni vulnerabilidades de seguridad -- esos son
  [`kdd-compliance-scan`](../kdd-compliance-scan/SKILL.md) y
  [`kdd-security-scan`](../kdd-security-scan/SKILL.md), dominios de politica
  distintos.
