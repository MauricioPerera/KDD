# Vendored from openai/codex-security

Estos 4 scripts se vendorizan (no se reescriben) desde
[openai/codex-security](https://github.com/openai/codex-security), commit
`9c7634b5d08b36e6060441fe3e35caaaf8aa6a49`, path
`sdk/typescript/_bundled_plugin/scripts/`. Licencia Apache-2.0 (ver
`LICENSE.codex-security` en este directorio; el resto del repo KDD es MIT — este
subdirectorio conserva su propia licencia de origen, patrón estándar de vendoring).

## Por qué son 4 archivos y no 1 (verificado por ejecución real, no por lectura)

`finalize_scan_contract.py` es el sellador determinista: valida `scan-manifest.json`
+ `findings.json` + `coverage.json` contra los 3 JSON Schemas de
`../../knowledge/data_models/security/`, deriva `findingId`/`occurrenceId`/fingerprints
de forma determinista, sella el manifest y proyecta `report.md` + SARIF.

Tiene dependencias duras NO obvias por lectura estática: carga otros scripts vía
`importlib.util.spec_from_file_location` (no son imports normales, no aparecen en un
análisis de imports estándar). El árbol real de dependencias, confirmado corriendo el
sello end-to-end (no solo leyendo el código):

```
finalize_scan_contract.py
  -> report_projection.py       (incondicional: genera report.md en todo sellado)
       -> validate_report_format.py   (cargado por report_projection.py)
  -> windows_scan_local_files.py       (fallback de I/O en Windows)
```

**Nota honesta de proceso:** el primer intento de vendorizar solo
`finalize_scan_contract.py` + `report_projection.py` pasó el smoke test inicial
porque se corrió desde el árbol original de `codex-security`, donde los archivos
hermanos faltantes seguían presentes al lado — el gap no se manifestó hasta correr
el finalizer vendorizado de forma aislada, que sí falló dos veces (una por
`windows_scan_local_files.py`, otra por `validate_report_format.py`, cargado a su
vez por `report_projection.py`) hasta llegar a este árbol completo. Un grep manual
de `importlib` en un solo archivo no alcanza para esta clase de dependencia; se
usó un rastreo transitivo automatizado (seguir cada `spec_from_file_location`
recursivamente) para confirmar que la lista de 4 es completa y no hay un quinto
salto.

## Qué NO se vendorizó (fuera de scope, no es necesario para el gate de CI)

El resto de `_bundled_plugin/scripts/` (workbench, deep-scan, config-preflight,
etc.) es infraestructura de la app de escritorio/MCP de Codex — no hace falta para
validar y sellar `findings.json`/`coverage.json` en un pipeline de CI.

## Actualizar la versión vendorizada

Repetir la copia desde un checkout de `openai/codex-security` en el commit
deseado, re-correr el rastreo transitivo de `importlib.util.spec_from_file_location`
por si el árbol de dependencias cambió, actualizar el hash de este README, y
re-correr `scripts/validate_security_findings.py` (Capa 3D) contra los fixtures
existentes para confirmar que el schema no cambió de forma incompatible.
