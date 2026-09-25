---
name: kdd-test-coverage-scan
description: Guia a cualquier agente (no depende de ningun modelo puntual) para producir un scan de gaps de cobertura de tests (rutas criticas sin cubrir, casos de error sin test, regresiones sin atrapar) en el formato de contrato de Capa 3 de KDD -- findings.json -- que despues gatea scripts/validate_test_coverage_findings.py. Usala cuando se pida auditar cobertura de tests fuera de un task contract CCDD, cruzar reportes de cobertura con criticidad, o se mencione "test coverage gaps", "untested critical path" o "Capa 3" en el contexto de este template. NO confundir con el oraculo congelado de CCDD (tests_sha256/test_command, ya Nivel 1 obligatorio).
---

# Test Coverage Scan (Capa 3 de KDD -- gaps de cobertura)

Produce hallazgos de gaps de cobertura de tests en el formato de contrato que
audita la Capa 3 de KDD. Esta skill NO es el gate -- es la parte
creativa/no determinista (identificar rutas criticas, cruzarlas con
reportes de cobertura y con el historial de incidentes, juzgar el impacto de
cada gap) que el gate despues valida. Distincion central: **el agente
decide QUE es un gap de cobertura; el gate solo audita que el artefacto
sellado cumpla forma y politica de calidad de datos.**

## Lee esto primero: la frontera con CCDD

**Antes de usar esta skill, confirma que lo que buscas NO ya lo cubre
CCDD.** CCDD (Nivel 1 obligatorio, sin activar nada) exige que todo
`task contract` en `knowledge/contracts/` tenga:

- un oraculo de tests congelado (`tests_sha256` en el frontmatter, gateado
  por `validate_contracts.py`);
- su `test_command` en verde (gateado por `validate_test_commands.py`).

Si tu pregunta es "¿esta funcion que se implemento via un task contract
tiene tests que pasan?", esa respuesta ya existe -- no necesitas esta
skill ni el dominio que gobierna.

Esta skill sirve para lo que CCDD deliberadamente NO cubre:

1. **Codigo que nunca paso por un task contract.** La mayoria de un
   proyecto real, sobre todo si KDD se adopto sobre un codebase
   preexistente.
2. **Gaps de TIPO de cobertura, no de presencia.** Un `test_command` en
   verde certifica que ESOS tests pasan, no que cubran el caso de error,
   la condicion de carrera, o el camino que revelo un incidente real.
3. **Test de regresion faltante tras un bug real ya corregido.**

Ver la seccion completa de frontera en
[`knowledge/data_models/test_coverage_findings.md`](../../../knowledge/data_models/test_coverage_findings.md).

## Cuando usarla

El usuario pide auditar si las rutas criticas de un sistema (dentro o fuera
de contratos CCDD) tienen el tipo de cobertura de tests que hace falta, y
quiere el resultado gobernado por KDD (versionable, gateado en CI, con
politica declarativa), no un reporte suelto en prosa.

## Insumos que necesitas antes de empezar

- `repo_root`: raiz del repositorio/producto a revisar.
- `scan_dir`: donde vas a escribir `findings.json`. Por defecto
  `test-coverage/scan` dentro del repo KDD (coincide con el default de
  `validate_test_coverage_findings.py`); si estas gobernando un repo
  EXTERNO, cualquier directorio disponible sirve, con tal de pasarselo
  explicito al gate.
- El schema completo vive en
  `knowledge/data_models/test-coverage/findings.schema.json` -- consultalo
  si dudas de un campo, no adivines la forma.

## Flujo

### 1. Identifica las rutas criticas

Antes de revisar codigo, fija por escrito (2-3 lineas) que operaciones son
criticas: las que mueven dinero, autentican usuarios, escriben datos
irreversibles, o cuyo fallo tendria el mayor costo. Esto acota donde
buscar.

### 2. Cruza rutas criticas con cobertura real

Si el proyecto genera reportes de cobertura (`coverage.py`/`pytest-cov`,
`nyc`/`c8`, `cargo-tarpaulin`, `go test -cover`), corre el reporte y
cruzalo con la lista de rutas criticas -- una linea "cubierta" segun el
reporte NO significa que el CASO relevante este probado (puede estar
cubierta por un happy-path que nunca ejercita el error). Sin reporte
automatizado, revision manual del codigo de test existente basta.

Clasifica cada gap real en `gapType`:

- `untested-critical-path`: la ruta critica no tiene NINGUN test que la
  ejercite.
- `no-error-case-coverage`: hay test del camino feliz, pero el manejo de
  error/excepcion de esa misma ruta no esta probado.
- `no-regression-test`: un bug real en produccion se corrigio sin agregar
  el test que lo hubiera atrapado.
- `flaky-test-untracked`: existe un test para la ruta, pero es intermitente
  y nadie lo esta arreglando -- efectivamente no cubre nada mientras
  siga flaky.

No inventes un finding para llenar un cupo: rutas criticas bien cubiertas
es un resultado valido, mismo criterio que los demas dominios de esta
familia.

Para cada gap real, junta ANTES de escribir el JSON:
- `location` exacta (archivo:funcion/metodo, o la operacion concreta);
- si es realmente una ruta critica (`criticalPath: true`);
- severidad honesta -- `untested-critical-path` en una ruta de pago es
  `critical`; un `no-error-case-coverage` en una zona de bajo impacto
  puede ser `low`;
- una remediacion CONCRETA y accionable para cualquier finding
  `critical`/`high` (no "agregar tests" a secas -- nombra que caso probar
  y donde; eso no pasa el gate de politica, que exige remediaciones
  sustantivas de >=20 caracteres para esos dos niveles).

### 3. Escribir el artefacto

En `<scan_dir>/findings.json`:

```json
{
  "documentType": "kdd-test-coverage.findings",
  "schemaVersion": "1.0",
  "scanId": "<identificador estable, p.ej. hash corto del commit + '_kdd-test-coverage-scan'>",
  "findings": [
    {
      "findingId": "cov_<ubicacion-slug>-<secuencial>",
      "gapType": "untested-critical-path",
      "location": "...",
      "criticalPath": true,
      "severity": "...",
      "remediation": "...",
      "source": "manual review | coverage report | incident postmortem"
    }
  ]
}
```

`findingId` es responsabilidad tuya (no hay finalizer que lo derive): usa
la ubicacion + un secuencial para que sea estable entre corridas del mismo
scan.

### 4. Gatear

```
python scripts/validate_test_coverage_findings.py <scan_dir>
```

`FAIL` con violaciones reales (`gapType`/`severity` fuera de enum,
remediacion tipo placeholder en un `critical`/`high`) significa que el
HALLAZGO esta mal capturado, no que el gate este mal -- volve al paso 2
para ese finding especifico, no debilites la regla en
`examples/rules/test-coverage-findings.rules.json` para que pase.

### 5. Reportar

Devolve al usuario la ruta de `findings.json` y un resumen: que rutas
criticas se revisaron, cuantos findings `critical`/`high` se sellaron.

## Que NO hace esta skill

- No reemplaza ni duplica el oraculo congelado de CCDD -- si la pregunta
  es sobre un `task contract` especifico, la respuesta ya la da
  `validate_contracts.py`/`validate_test_commands.py`, sin esta skill.
- No verifica que un test de regresion REALMENTE hubiera atrapado el bug
  original (eso exige revertir la correccion y confirmar que el test
  falla) -- fuera del artefacto sellado (ver el `code_only` de
  `test-coverage-findings.rules.json`).
- No audita seguridad, licencias, privacidad, accesibilidad, vigencia de
  dependencias ni observabilidad -- esos son otros dominios de esta misma
  familia.
