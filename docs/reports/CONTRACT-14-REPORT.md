# CONTRACT-14 — Versionado de la plantilla: CHANGELOG, upgrade y primer release — REPORT

Fecha: 2026-07-07
Spec: `specs/CONTRACT-14-versionado-plantilla.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| `test_versioning.py` | ✅ OK (3 tests, sin skips) | corrida PM |
| Validadores OKF + contratos | ✅ exit 0 (18 nodos; 10 contratos con hash re-sellado que el PM recalculó y coincide) | corrida PM |
| Menciones de CHANGELOG en README | ✅ 2 (EN y ES) | grep PM |
| Mutación PM | ✅ quitar la mención ES → test rojo nombrando la mitad ES; restaurar → verde | mutación propia del PM sobre README |
| Tag en remoto | ✅ `git ls-remote --tags origin v1.0.0` → `afed575...` | corrida PM |
| Suite `unittest` | ✅ verde 2× (integrada con C15: **181 tests**) | corridas del PM sobre el estado final del batch |
| CI | ✅ ambas patas en success | run del push de cierre del batch |

## VERSIONADO / T1 (commit `2e4af38` · tag `v1.0.0` creado por el PM)

`CHANGELOG.md` con entrada semver `v1.0.0 — 2026-07-07` e historia retroactiva C01→C13
rastreable a `docs/reports/` (spot-check del PM: entradas enlazan su reporte);
`knowledge/plantilla-upgrade.md` (Concept, enlazado desde el index) con INFRA
sobreescribible vs propiedad del proyecto y procedimiento manual de upgrade (re-validar
con gates, re-sellar hashes si cambian tests de infra — nunca merge ciego); README EN/ES
con la subsección de versionado; `tests/test_versioning.py` fija la coherencia
CHANGELOG↔README↔nodo. Sin re-delegaciones.

## Verificación final del PM (independiente del dev)

- Los 5 comandos de criterios re-corridos por el PM (tabla).
- Mutación adversarial propia sobre el README (mitad ES) → rojo con mensaje correcto.
- `tests_sha256` recalculado por el PM → coincide con el re-sellado del dev.
- Tag verificado en REMOTO, no solo local.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C14-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. Próximos releases: entrada nueva en CHANGELOG + tag, según el procedimiento del
nodo de upgrade.
