# CONTRACT-03 — Validador OKF: hacer cumplir la spec sobre toda la KB — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-03-validador-okf.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| `validate_okf.py knowledge` sobre la KB real | ✅ exit 0 — 9 nodos conformes, 0 errores | corrida PM |
| Validador de contratos | ✅ exit 0 (4 contratos) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**60 tests**: 41 + 19 nuevos) | corridas PM idénticas |
| Mutaciones | ✅ huérfano → exit 1 nombrándolo; type inválido + enlace roto → exit 1 con ambos hallazgos | mutaciones del dev Y reproducidas por el PM sobre copia |
| Regla 7 (C02) cumplida | ✅ el dev ensambló su contexto con `assemble_context.py` y pegó el reporte de slots en su evidencia | `.agents/logs/validate-okf-REPORT.md` |
| CI | ✅ paso "Validate OKF nodes" agregado; pasos existentes intactos (diff +3) | diff PM |

## Entregado (`22b2145`, implementado por agente efímero contra el task contract)

`scripts/validate_okf.py` — la [Especificación OKF](../../knowledge/OKF-SPEC.md) convertida
en gate determinista sobre `knowledge/**/*.md` (stdlib puro, espejo del patrón de
`validate_contracts.py`): §1-§2 frontmatter parseable con `type/title/description/tags`
(tags no vacías, minúsculas); §3 tipos cerrados; §4 enlaces relativos internos resuelven a
archivo existente; §5 alcanzabilidad desde `index.md` (directa o vía carpeta) — huérfano =
ERROR. CLI con exit 0/1 y resumen. 19 tests con fixtures en tempdir + test contra la KB
real. El dev no tocó ningún nodo existente: la KB no tenía violaciones reales.

Task contract: `knowledge/contracts/validate-okf.md`. Evidencia de tarea:
`.agents/logs/validate-okf-REPORT.md` (local, gitignorada).

**Hito de dogfooding:** primera delegación que consume el ensamblador de contexto (C01)
por mandato de la regla 7 (C02) — el ciclo completo de la plantilla usado por la propia
plantilla.

## Verificación final del PM (independiente del agente)

- `validate_okf` + `validate_contracts` + suite 2× (60/60 ambas): ejecutados por el PM.
- Mutaciones reproducidas por el PM sobre una copia de la KB (nunca sobre la real):
  nodo `solitario.md` sin enlace → exit 1 nombrándolo; nodo con `type: 'TipoInventado'` y
  `[roto](./no-existe.md)` → exit 1 con los dos findings.

## Pendientes / ítems de seguimiento

Ninguno. Candidato a C04 (ya identificado): dogfood E2E — una feature real implementada
vía task contract + contexto ensamblado + agente efímero como caso resuelto de referencia.
