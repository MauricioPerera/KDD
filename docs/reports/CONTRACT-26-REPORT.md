# CONTRACT-26 — Cableado de agentes — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-26-agent-wiring.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del checker (12) | ✅ verde sin modificarlo (sello `47d4c061...`) | corrida PM |
| Gate de rules | ✅ `0 error(es) en 6 archivo(s)` — dominio nuevo con REPRO verde | corrida PM |
| Cross-check FRONTERA | ✅ los 2 casos `code_only_miss` (skill y server fantasma), invisibles al declarativo, atrapados por el checker con el mensaje canónico exacto | corrida PM |
| Mutación PM: modelo inválido en golden | ✅ REPRO divergence exacta (`expected=[], actual=['agents']`), exit 1 — mutación confirmada por print antes de medir | copia mutada re-sellada |
| Canarios (5 goldens previos) | ✅ byte-intactos | corrida PM |
| 6 gates | ✅ exit 0 (18 contratos, 34 nodos, 26 specs, 6 rule-sets, 6 skills) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**327 tests**) | corridas PM |
| Post-init neutral | ✅ los 6 artefactos nuevos al MANIFEST | `test_init_project` en suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra (¿se puede contratar un agente?)

Respuesta en tres capas, cada una con su decisión honesta:

1. **Definiciones del agente**: el RECON encontró CERO archivos de definición reales (ni
   `~/.claude/agents/` ni `.claude/agents/`). El gate estilo C24 NO se construyó — la
   doctrina evidencia-primero aplica a gates igual que a familias. Queda anotado en el
   nodo para cuando el activo exista.
2. **El cableado** (este contrato): qué agente usa qué skills, qué servidores MCP, modelo
   permitido y la política real de máximo 2 re-delegaciones como `bounds`. Datos
   sintéticos modelados sobre el flujo PM-nativo real.
3. **El comportamiento**: no contratable determinísticamente — y esa es la TESIS de CCDD:
   no se contrata al agente, se contrata el artefacto que produce. El dev haiku de este
   mismo contrato es la demostración en vivo.

**Quinta clase de frontera medida**: integridad referencial bajo cuantificación ("la skill
referenciada debe EXISTIR en el registro" — `refs` no opera dentro de `each`). Primera
aparición ⇒ sin familia nueva; declarada `code_only` y cerrada por código
(`check_agent_wiring`, precedente C22). El cierre encadena de facto el triángulo con los
gates de C24 (skills) y C25 (registro MCP).

## Verificación final del PM (independiente del dev)

- Oráculo 12/12 con sello intacto; cross-check de frontera; mutación observable matada;
  gates 6/6; suite 2× 327/327; canarios byte-intactos.
- Perímetro del dev limpio: SOLO `src/check_agent_wiring.py`; sin re-delegaciones.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C26-REPORT.md`.

## Pendientes / ítems de seguimiento

- Gate de definiciones de agente (capa 1): pendiente de que EXISTA el activo real.
- Familia `refs`-en-`each`: se agrega solo si la clase repite en otro dominio.
