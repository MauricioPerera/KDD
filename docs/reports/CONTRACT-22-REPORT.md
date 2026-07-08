# CONTRACT-22 — Checker de ciclos de grafo — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-22-graph-cycles.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del checker (12) | ✅ verde sin modificarlo (sello `c1740621...`) | corrida PM |
| **Verificación cruzada**: el caso FRONTERA del golden de C20 | ✅ `find_graph_cycles` devuelve exactamente 1 ciclo (`A -> B -> A`) — el código ve lo que el declarativo declaró no ver | corrida PM |
| Adversarial (grafos propios del PM) | ✅ diamante doble sin falso positivo; ciclo escondido tras convergencia detectado; dos ciclos compartiendo nodo, ambos canónicos; nombres invertidos → misma forma canónica; malformado no oculta ciclos reales | fixtures del PM |
| Gate de rule contracts | ✅ 4/4 dominios byte-intactos (este contrato no tocó rule-sets) | corrida PM |
| Validadores + lint | ✅ exit 0 (15 contratos, 28 nodos, 22 specs) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**260 tests**) | corridas PM |
| Post-init neutral | ✅ checker + oráculo + contrato al MANIFEST | `test_init_project` en suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

La frontera #1 del dominio workflows ("ningún ciclo entre nodos", propiedad global del
grafo que las familias declarativas no expresan) quedó **cerrada por la vía que la
doctrina manda**: un task contract de código con oráculo congelado. El dominio workflows
tiene ahora la dupla completa — rule contract para lo uniforme (C20) + task contract para
lo global (C22) — igual que ruteo la tiene desde C21. En el rule-set, la regla sigue
declarada `code_only`: eso es exactamente lo que significa, y ahora ese código existe.

Detalles de diseño que el oráculo congeló: forma canónica de ciclo (rotado al nodo
lexicográficamente menor, reportado una sola vez — sin inflar conteos con rotaciones),
convergencia ≠ ciclo (el diamante, falso positivo clásico del DFS que confunde "visitado"
con "en el camino"), y lo malformado se salta sin ocultar ciclos reales (la FORMA la
valida el rule contract del dominio; los ciclos, este checker — composición sin pisarse).

## Verificación final del PM (independiente del dev)

- Oráculo 12/12; verificación cruzada del criterio en verde; adversarial propio (arriba).
- Gate 4/4; validadores + lint exit 0; suite 2× consecutivas 260/260.
- Perímetro limpio (el dev tocó solo `src/check_workflow_graph.py`); sin re-delegaciones;
  implementación DFS 3-colores, dentro del budget.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C22-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. Con C20+C21+C22, el `Unreleased` acumula: familia `each` + dominio workflows +
patrón evento→decisión en dos formas + frontera de grafo cerrada — contenido de sobra
para v1.2.0 cuando se decida cortar.
