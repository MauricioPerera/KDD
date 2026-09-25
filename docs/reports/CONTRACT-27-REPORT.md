# CONTRACT-27 — Gate de coherencia CHANGELOG↔reportes — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-27-changelog-gate.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del gate (14) | ✅ verde sin modificarlo (sello `9e608944...`) | corrida PM |
| Gate sobre el repo REAL | ✅ `0 error(es), 27 contrato(s) verificados`, exit 0 | corrida PM |
| Mutación PM: entrada borrada | ✅ borré la entrada de **C21 — una de las tres perdidas en el incidente real** — `ENTRY_MISSING` nombrando NN y archivo, exit 1 | copia mutada, aplicación confirmada por print |
| Mutación PM: entrada fantasma | ✅ `**Contract 99` sin reporte → `REPORT_MISSING`, exit 1 | copia mutada |
| 6 gates previos | ✅ exit 0 (19 contratos, 35 nodos, 27 specs, 6 rule-sets, 6 skills) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**341 tests**) | corridas PM |
| Auto-validación | ✅ la propia entrada de C27 en Unreleased, con su link, pasa por el gate que describe | corrida PM |
| CI (8º paso nuevo) | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

El ciclo completo incidente → regla humana → gate determinista. En v1.2.0, tres entradas
del CHANGELOG se perdieron por un `str.replace` que falló en silencio; la regla operativa
que salió de ahí ("grep de presencia antes de commitear") dependía de disciplina humana.
Este gate la vuelve CI: reporte sin entrada (`ENTRY_MISSING` — LA clase del incidente),
entrada sin reporte (`REPORT_MISSING`), entrada sin link (`LINK_MISSING`) y duplicados
(`ENTRY_DUP`) rompen el build en ambas patas. La mutación de verificación reprodujo el
incidente original literalmente (borrar la entrada de C21) y el gate lo atrapó.

Capa opcional coherente con la doctrina: proyectos instanciados sin CHANGELOG o sin
historia de reportes pasan con INFO. El incidente quedó además documentado en
`knowledge/casos-reales.md` (caso `replace-silencioso-en-docs`) con el puntero al gate.

## Verificación final del PM (independiente del dev)

- Oráculo 14/14 con sello intacto; mutaciones observables matadas; 7 gates; suite 2×
  341/341; perímetro del dev limpio (SOLO `scripts/validate_changelog.py`); sin
  re-delegaciones.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C27-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. Los dos ítems restantes del backlog siguen condicionados a evidencia: gate de
definiciones de agente (cuando exista el activo) y familia `refs`-en-`each` (si la clase
repite).
