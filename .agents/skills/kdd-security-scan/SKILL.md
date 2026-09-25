---
name: kdd-security-scan
description: Guia a cualquier agente (no depende de Codex ni de un modelo puntual) para producir un scan de seguridad de un repositorio en el formato de contrato de Capa 3 de KDD -- scan-manifest.json, findings.json, coverage.json -- que despues sella scripts/vendor/codex-security/finalize_scan_contract.py y gatea scripts/validate_security_findings.py. Usala cuando se pida auditar/escanear un repo por vulnerabilidades bajo gobernanza KDD, o se mencione "security scan", "Capa 3", "findings.json" o "hallazgo de seguridad" en el contexto de este template.
---

# Security Scan (Capa 3 de KDD)

Produce hallazgos de seguridad de un repositorio en el formato de contrato que audita
la Capa 3 de KDD. Esta skill NO es el gate -- es la parte creativa/no determinista
(la hace un LLM, con o sin subagentes) que el gate despues valida. Distincion central:
**el agente decide QUE es un hallazgo; el gate solo audita que el artefacto sellado
cumpla forma y politica.** Ningun LLM participa en el gate.

Adaptada del flujo de las skills de
[openai/codex-security](https://github.com/openai/codex-security)
(`_bundled_plugin/skills/security-scan/`, Apache-2.0), quitando toda dependencia del
binario `codex` y de sus tools MCP especificas de la app de escritorio. Esta version
corre con Bash + lectura de archivos nada mas -- cualquier agente sirve.

## Cuando usarla

El usuario pide auditar un repo (propio o externo) por vulnerabilidades y quiere el
resultado gobernado por KDD (versionable, gateado en CI, con politica declarativa),
no un reporte suelto en prosa.

## Insumos que necesitas antes de empezar

- `repo_root`: raiz del repositorio a escanear (puede ser un clon separado del propio
  KDD -- ver la nota de portabilidad en `scripts/vendor/codex-security/README.md`,
  el finalizer no asume que el target viva dentro del repo KDD).
- `scan_dir`: donde vas a escribir los 3 JSON. Por defecto `security/scan` dentro del
  repo KDD (coincide con el default de `validate_security_findings.py`); si estas
  gobernando un repo EXTERNO, cualquier directorio disponible sirve, con tal de que
  se lo pases explicito a `finalize_scan_contract.py --scan-dir`.
- Los 3 schemas viven en `knowledge/data_models/security/` (vendorizados del mismo
  origen, no los reinventes ni los edites).

## Flujo

### 1. Alcance

Antes de tocar codigo, fija por escrito (2-3 lineas, no hace falta un documento
aparte): que directorio/paquete se revisa, que queda explicitamente fuera, y contra
que amenaza (codigo de terceros ejecutado localmente, superficie de red expuesta,
manejo de secretos, etc.). Esto se vuelca en `scan.scope.summary` del manifest.

### 2. Descubrimiento

Recorre el `repo_root` en el alcance fijado. Por cada archivo relevante, evalua las
clases de riesgo que apliquen al lenguaje (inyeccion de comandos/SQL, path traversal,
deserializacion insegura, secretos hardcodeados, control de acceso, TOCTOU, etc.).
No inventes un hallazgo para llenar un cupo: un scan con cero findings y coverage
`complete` es un resultado valido y se sella igual.

Para cada candidato real, junta ANTES de escribir el JSON:
- la ubicacion exacta (archivo:linea-linea) del sink y, si aplica, del source:
- por que es explotable (flujo de datos concreto, no "podria ser inseguro");
- severidad y **confianza** honestas -- una confianza `high` en un finding `critical`
  es una afirmacion fuerte; si tenes dudas reales, la confianza va en `medium`/`low`
  (ver la regla de politica mas abajo, que exige `high` para todo `critical`).
- al menos un CWE de la taxonomia estandar.
- una remediacion CONCRETA y accionable (no "revisar el codigo" -- eso no pasa el
  gate de politica, que exige remediaciones sustantivas).

### 3. Escribir los 3 artefactos (DRAFT, sin sellar)

En `<scan_dir>/`, escribi:

- **`scan-manifest.json`**: `documentType`, `schemaVersion: "1.0"`, y `scan` con
  `id`, `producer` (identificate como el agente real que hizo el analisis, NUNCA
  como "codex" -- ver la nota de honestidad abajo), `status: "completed"`,
  timestamps, `target` (kind/targetId/displayName + `revision` si es git_revision),
  `scope`, `coverageRef: "coverage.json"`, `findingsRef: "findings.json"`. Dejalo SIN
  `sealedAt` ni `scan.artifacts` -- eso lo llena el finalizer.
- **`findings.json`**: `documentType`, `schemaVersion`, `scanId` (igual a `scan.id`
  del manifest), y `findings[]` con `findingId`/`occurrenceId` en `"draft"` (el
  finalizer los deriva) y el resto de los campos completos: `ruleId`, `identity`,
  `title`, `summary`, `severity`, `confidence`, `taxonomy`, `locations`,
  `remediation`, `provenance.source`.
- **`coverage.json`**: `documentType`, `schemaVersion`, `scanId`, `mode`,
  `completeness`, `inventoryStrategy`, `includePaths`, `excludePaths`, `surfaces[]`
  (una entrada por superficie revisada con `disposition` real), `explicitExclusions`,
  `deferred`.

Los 3 schemas completos estan en `knowledge/data_models/security/*.schema.json` --
consultalos si dudas de un campo, no adivines la forma.

### 4. Sellar

```
python scripts/vendor/codex-security/finalize_scan_contract.py \
  --scan-dir <scan_dir_absoluto_canonico> \
  --schema-dir knowledge/data_models/security \
  --source-root <repo_root_absoluto_canonico>
```

**`--scan-dir` y `--source-root` tienen que ser rutas ABSOLUTAS y canonicas (sin
`..`, sin symlinks).** El finalizer compara `path.absolute()` contra
`path.resolve(strict=True)` y rechaza cualquier discrepancia
(`_require_scan_directory`) -- una ruta relativa con `..` (p.ej. `../mi-scan`) falla
con `error: scan directory: expected a canonical non-symlink directory` (exit 2),
aunque el directorio exista y sea perfectamente valido. Resolve la ruta antes de
llamarlo (`realpath` en shells POSIX/Git-Bash, `Resolve-Path` en PowerShell) en vez
de pasarla relativa.

Si falla por JSON Schema invalido, el error dice exactamente que campo -- corregi el
draft y reintenta. NO edites el finalizer para que pase; el error es del draft.

### 5. Gatear

```
python scripts/validate_security_findings.py <scan_dir>
```

`FAIL` con violaciones reales (CWE faltante, remediacion tipo placeholder, `critical`
con confianza no-`high`) significa que el HALLAZGO esta mal capturado, no que el
gate este mal -- volve al paso 2 para ese finding especifico, no debilites la regla
en `examples/rules/security-findings.rules.json` para que pase.

### 6. Reportar

`<scan_dir>/report.md` y `<scan_dir>/exports/results.sarif` ya estan generados por el
finalizer -- no los escribas a mano. Devolve al usuario la ruta de `report.md` y el
resumen de severidades.

## Honestidad sobre la procedencia (`producer` / `provenance.source`)

Nunca declares `producer.name` como si fuera Codex o cualquier otro agente que no
corrio el analisis. Identificate como lo que sos (p.ej. `"claude-sonnet-5 (KDD
kdd-security-scan skill)"`, `"glm-5.2 via pm-glm-ccdd"`). El campo existe justamente
para que quien lea el sello sepa que motor de razonamiento genero el hallazgo -- un
dato de confianza real, no un detalle cosmetico.

## Que NO hace esta skill

- No reemplaza una auditoria humana para hallazgos `critical` de alto impacto real --
  produce el artefacto gobernable, la decision de remediar/aceptar el riesgo sigue
  siendo humana (por eso el estado de triage vive fuera del artefacto sellado, ver el
  `code_only` de `security-findings.rules.json`).
- No escanea binarios ni dependencias de terceros (supply-chain) -- eso es un dominio
  de politica distinto, no cubierto por `security-findings.rules.json` tal como esta.
