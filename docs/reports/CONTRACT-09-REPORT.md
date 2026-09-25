# CONTRACT-09 — Validador de contratos de ejecución — REPORT

Fecha: 2026-07-05
Spec: `specs/CONTRACT-09-validador-specs.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| `python scripts/validate_specs.py specs` | ✅ | `Resumen: 0 error(es) en 9 archivo(s)`, exit 0 |
| Suite `unittest` | ✅ verde 2× (131 tests) | corridas del PM sobre el estado final |
| Validador de contratos | ✅ | `0 error(es), 0 warning(s) en 8 archivo(s)` (incluye `validate-specs.md`) |
| Validador OKF | ✅ | `0 error(es), 0 warning(s) en 13 archivo(s)` |
| `validate.yml` con paso nuevo + YAML parsea | ✅ | `yaml.safe_load` sin excepción; paso `"Validate specs contracts"` añadido sin tocar los existentes |
| Ensamblador de contexto (smoke) | ✅ | `guardrails: ok` |

## VALIDATE-SPECS (T1)

Se entregó `scripts/validate_specs.py` (stdlib, sin red, sin subprocess; interfaz y
formato de salida espejo de `validate_okf.py`), `tests/test_validate_specs.py` (10 tests,
casos congelados en el contrato), el paso nuevo de CI, la mención bilingüe en el README y
el task contract `knowledge/contracts/validate-specs.md`.

Regla cerrado/abierto: un contrato con `docs/reports/CONTRACT-NN-REPORT.md` es cerrado y
solo se le exige el baseline (criterios con comando entre backticks + Restricciones); los
abiertos deben además tener `Tocar SOLO` y `ABORTAR SI` rellenado sin placeholders. Los
contratos históricos 01-08 pasan sin ediciones.

Trade-offs aceptados: rutas de findings relativas al padre del dir de specs (consistente
con `validate_okf.py`); "comando entre backticks" = code span no vacío en un checkbox.

## Verificación final del PM (independiente del dev)

- Los 4 pasos del CI + validador nuevo re-corridos por el PM: todos exit 0.
- Suite 2× consecutivas: OK ambas, exit 0.
- Demo adversarial con fixtures propios del PM (no los del dev): contrato abierto sin
  `ABORTAR SI` → `ERROR [ABORTAR]`; abierto con placeholder de ángulo → `ERROR [ABORTAR]`;
  cerrado sin `ABORTAR SI` ni `Tocar SOLO` → pasa. Exit 1 con 2 error(es) en 3 archivo(s).
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/VALIDATE-SPECS-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno.
