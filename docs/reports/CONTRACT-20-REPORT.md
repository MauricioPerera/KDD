# CONTRACT-20 — Workflows como dominio + familia `each` — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-20-workflow-policy.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del motor (actualizado con `each`, re-sellado) | ✅ verde, 6 tests nuevos de TestEach | corrida PM |
| **Gate sobre los 3 dominios** | ✅ `Resumen: 0 error(es) en 3 archivo(s)` — pagos y fronteras byte-intactos (canario de regresión vía REPRO) + workflows | corrida PM |
| Regresión de equivalencia (pagos) | ✅ OK | corrida PM |
| Mutación: workflow inválido marcado válido + golden RE-SELLADO | ✅ `REPRO` | mutación PM sobre copia |
| Mutación: golden aflojado sin re-sellar | ✅ `GOLDEN_FROZEN` | mutación PM |
| 4 validadores + lint | ✅ exit 0 (25 nodos, 20 specs) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**239 tests**) | corridas PM |
| Post-init neutral | ✅ los 3 artefactos de workflows al MANIFEST | `test_init_project` en suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué quedó

**Familia `each`** (motor, dev efímero): cuantificación ∀ sobre colecciones —
`{collection, where?, rules}` con subset interno v1 (`required/type/enums/bounds`),
violaciones con prefijo de la colección (el matching del golden funciona sin tocar el
gate), colección ausente/no-lista se salta, byte-compatibilidad total con las familias
existentes (los goldens previos no cambiaron y REPRO los re-verificó). Sin re-delegaciones.

**Dominio workflow-policy** (orquestador): política de workflows con forma n8n —
escalares (`error_workflow` requerido, `execution_timeout` acotado POR ENTORNO vía
`keyed_bounds`), por-nodo vía `each` (todo `httpRequest` con timeout, cero credenciales
inline, tipos de nodo permitidos), 12 casos golden sellados. Con esto, la parte mecánica
de una auditoría de workflows (la clase de checks de `n8n-audit`) es expresable como gate
determinista.

## La evidencia que justificó la extensión (doctrina cumplida, no esquivada)

`each` NO se agregó especulativamente: el RECON demostró con salidas reales que las reglas
por-nodo eran inexpresables Y que forzarlas con paths punteados producía falsos positivos
en todo workflow. Tres dominios, y el mapa de fronteras quedó así:
1. **Cross-field / identidad** (pagos: `is True`; fronteras: `require-field-match`) —
   sigue `code_only`.
2. **Cuantificación sobre colecciones** — CERRADA por `each` en este contrato (game-protocol
   ya la resolvía con familias collection-based: el patrón estaba probado).
3. **Propiedades globales del grafo** (ciclos en `connections`) — nueva, medida acá,
   queda `code_only` (recorrido de grafo es territorio de task contract; no se infló
   `each` para taparla).

## Verificación final del PM (independiente del dev)

- Oráculo del motor verde (incluidos los 6 de `each`); gate 3/3 dominios exit 0;
  equivalencia de pagos OK (regresión).
- Mutaciones exactas, incluida la crítica (sello válido + semántica rota → `REPRO`).
- 4 validadores + lint exit 0; suite 2× consecutivas 239/239.
- Nota de proceso: una inserción por heredoc del PM falló en silencio sobre el contrato
  del motor; la cazó un grep de presencia pre-delegación y se corrigió con el editor —
  el andamiaje también se verifica, no se asume.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C20-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno bloqueante. Candidatos con evidencia parcial (esperan un dominio más, según la
doctrina): familias keyed dentro del subset de `each` (tipos de nodo POR entorno) y
checker de ciclos de grafo como task contract de ejemplo.
