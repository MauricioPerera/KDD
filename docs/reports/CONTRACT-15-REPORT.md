# CONTRACT-15 — Ensamblador a escala: ranking, corte honesto por nodo y chars/token configurable — REPORT

Fecha: 2026-07-07
Spec: `specs/CONTRACT-15-ensamblador-ranking.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| `test_assemble_context.py` | ✅ OK (36 tests) | corrida PM |
| Smoke del CI | ✅ exit 0; 2 invocaciones → `cmp` idéntico | corrida PM |
| Fallback holgado byte-idéntico | ✅ código viejo vs nuevo sobre la MISMA KB → idéntico | corrida PM (el primer intento de comparación del PM usó KBs distintas — falso rojo, corregido) |
| Mutación PM (fixture propio, KB 4 nodos, budget justo) | ✅ `selected` = universo (4), `cut=beta`, `omitted=[delta,gamma]`, partición exacta; holgado → sin claves | fixture del PM, no del dev |
| Validador de contratos + lint ASCII | ✅ exit 0 (hash re-sellado recalculado por el PM, coincide) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**181 tests**: 169 + 12 del batch C14+C15) | corridas del PM sobre el estado final |
| CI | ✅ ambas patas en success | run del push de cierre |

## ASSEMBLE-RANK / T1 (commit `76864b5`)

Las 4 decisiones fijadas en el spec: ranking determinista (mención=2, tag=1, empate
alfabético) que gobierna el orden de ensamblado; corte POR NODO (enteros mientras caben,
el primero que no cabe se compacta, el resto se omite) en vez de compactar la
concatenación; reporte honesto (`selected` = universo recuperado, `cut` y `omitted_nodes`
como subconjuntos, ausentes cuando no aplica, visibles en la línea del slot del CLI);
`budget.chars_per_token` opcional compartido entre `_tokens` y `_compact` desde un solo
lugar. `ccdd/context.json` intacto.

**Hallazgo destapado por el reporte honesto:** el smoke del CI ya venía cortando nodos en
silencio (slot `okf_nodes` con tope 6000 sobre una KB que creció) — ahora la línea del
slot lo declara: `cut=index`, 12 nodos omitidos. El comportamiento no cambió; la
visibilidad sí.

## Historia de la tarea (2 re-delegaciones — el tope de la política, ambas por veredicto del PM)

1. **Entrega 1**: `cut`/`omitted_nodes` se calculaban en el helper interno pero nunca
   llegaban al slot report — los tests del dev asertaban el helper, el fixture del PM
   asertó el REPORTE y lo cazó (la clase "comando cumplido sin cumplir la intención").
2. **Entrega 2**: reporte cableado, pero `selected` perdió la compat fijada en el spec
   (emitía solo los incluidos enteros: el smoke mostraba 5 de 18 recuperados) — desvío no
   declarado contra decisión fijada.
3. **Entrega 3 (v3)**: `selected` = universo recuperado; aserción de partición
   (`selected = incluidos ∪ {cut} ∪ omitidos`) congelada en tests.

## Verificación final del PM (independiente del dev)

- Fixture propio de 4 nodos: partición exacta, claves ausentes en holgado.
- Byte-idéntico holgado verificado ejecutando el código VIEJO (de la copia pre-C15) y el
  nuevo sobre la misma KB temporal.
- Smoke exit 0, determinista 2×, `selected` con los 18 nodos.
- Hash re-sellado recalculado; 4 gates exit 0; suite 2× consecutivas 181/181.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C15-REPORT.md`.

## Pendientes / ítems de seguimiento

Observación heredada del retriever (pre-C15, sin cambios): el match por nombre es por
substring (`gamma` matchea dentro de `beta_gamma_doc`), lo que puede inflar el score de
nodos con nombres contenidos en otros. No bloqueó ningún criterio; candidato a ajuste
futuro (match por palabra completa) si molesta en KBs reales.
