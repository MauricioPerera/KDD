# Auditoría de cierres históricos de proyecto

Fecha: 2026-09-25. Alcance: `specs/CONTRACT-01` a `CONTRACT-33`, sus reportes en `docs/reports/` y la política `completion-legacy.json`.

## Resultado

`python scripts/validate_completion.py` informa `PASS=0 FAIL=0 SKIP=33`. Los 33 pares conservan el digest registrado en la política. SKIP significa que el cierre histórico no está acreditado por el esquema de evidencia actual; no equivale a PASS.

La revisión de los 33 reportes y specs encontró:

| Evidencia requerida para migrar | Pares que la incluyen |
| --- | ---: |
| URL de un run de GitHub Actions del repositorio | 0 |
| SHA completo del commit evaluado en el reporte | 0 |
| Manifiesto `CONTRACT-NN-EVIDENCE.json` | 0 |
| Criterios con ID `AC-*` o `CI-*` en el spec | 0 |

Por ello no se promociona ningún par histórico a `verified_in_ci`. Los CI actuales validan el repositorio actual; no demuestran retrospectivamente los criterios originales de cada contrato.

## Migración futura

Cada par solo podrá salir de SKIP con criterios de aceptación identificados y comprobables, evidencia concreta por criterio, un run de CI cuyo resultado y SHA se hayan verificado, y un reporte que enlace ese mismo run. Los cambios legítimos al spec o reporte exigirán retirar su excepción histórica y pasar `scripts/validate_completion.py` con el nuevo manifiesto.
