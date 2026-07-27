---
name: pm-native-ccdd
description: 'Variante NATIVA del PM/orquestador CCDD que usa sub-agentes de la app de Claude (tool Agent con model override) en vez de GLM/Ollama externo. Claude autora contrato + tests congelados (oráculo), delega la IMPLEMENTACIÓN a un sub-agente barato (Haiku 4.5), y verifica por el gate CCDD determinista. Úsala cuando quieras el flujo PM+CCDD sin la fragilidad de ollama, con aislamiento por worktree para paralelismo y reintentos con contexto vía SendMessage. Hermana de pm-glm-ccdd (misma metodología; cambia SOLO el mecanismo de delegación). Deslinde con pm-sonnet-opus-haiku: mismo gate CCDD/KDD como verificador si el repo lo trae, pero tiering de implementador distinto — esta usa Haiku barato con escalado a Sonnet; pm-sonnet-opus-haiku usa Opus fijo (más caro) más QA/verificación adversarial opcional en capas. Elegí ESTA para el flujo 100% CCDD con implementador barato; usá pm-sonnet-opus-haiku si preferís implementador Opus + QA por capas.'
---

# PM nativo · Devs = sub-agentes de la app (Agent + model override) · QA = CCDD gate

Misma metodología CCDD que [pm-glm-ccdd](../pm-glm-ccdd/SKILL.md) — contrato + tests congelados
autorados ANTES de delegar, verify-by-artifact, política de reintentos, red-team del HECHO,
suite 2x. **Lo único que cambia es el mecanismo de delegación**: en vez de `ollama launch`
(GLM externo), el implementador es un **sub-agente nativo** vía la tool `Agent`.

## Tiering (los cuatro tiers, nativos)
- **Triage → Haiku 4.5** (`Agent`, `model:"haiku"`): leer issue, clasificar, limpiar log, mapear
  tools MCP, detectar si ya está hecho. Cortá el pipeline aquí si no hay trabajo.
- **PM/oráculo → Sonnet 5** (`model:"sonnet"`) por defecto; **Opus** solo para oráculos
  adversariales sin tropo conocido. Autora contrato + tests congelados + lint + baseline rojo.
- **Dev/implementador → Haiku 4.5** (`model:"haiku"`), escalá a `model:"sonnet"` una función
  puntual si Haiku falla el gate 2×.
- **Gate/verify → el orquestador** (vos): corrés `mcp__ccdd-complexity__*` + re-corrés los tests.

## Cómo invocar cada agente (native)

**Triage / PM / Dev — tool `Agent`:**
```
Agent({ subagent_type: "claude", model: "haiku"|"sonnet"|"opus",
        run_in_background: true, isolation: "worktree" (solo devs en paralelo),
        description: "<3-5 palabras>", prompt: "<spec autocontenida>" })
```
- El resultado (texto final del agente) vuelve como tool result; el harness reporta
  `subagent_tokens` / `tool_uses` / `duration_ms` en la notificación → **medición de costo exacta**.
- `run_in_background: true` para no bloquear (llega notificación al terminar).

**Paralelismo sin colisión — `isolation: "worktree"`:**
- Cada dev en su propio git worktree → NO necesitás declarar "archivos disjuntos" (lo resuelve
  el aislamiento). Auto-limpiado si no cambió. Coste ~200-500ms + disco por agente: úsalo SOLO
  cuando varios devs mutan archivos a la vez; para tareas secuenciales, omitilo.

**Reintento tras FAIL — `SendMessage` al MISMO dev (conserva contexto):**
```
SendMessage({ to: "<agentId>", summary: "gate FAIL: cyclomatic 12>10",
              ... "extraé helpers, no toques los tests, re-corré node --test" })
```
- Más barato que un `Agent` nuevo: el dev ya tiene el contexto de la tarea; solo le pasás el
  feedback del gate. (En pm-glm-ccdd cada retry re-lanzaba GLM re-enviando toda la spec.)

**Fan-out determinista — tool `Workflow`** (requiere opt-in explícito del usuario/ultracode):
- Encodeá el pipeline como script: `pipeline(tareas, stagePM, stageDev, stageVerify)` con
  `agent(prompt, {model:"haiku", isolation:"worktree", effort:"low"})`; `parallel()` para
  verificación adversarial (N escépticos por hallazgo). El tiering se expresa por-agente con
  `model:` y `effort:` (`low` mecánico, `high`/`max` oráculo difícil).

## Flujo
1. **Triage** (Haiku) → clasifica y decide si hay trabajo.
2. **PLAN/DECOMP** (orquestador) → tareas atómicas.
3. Por tarea: **contrato + tests congelados** (Sonnet) → lint (`lint_task_contract`) → baseline rojo.
4. **Delegar impl** (Haiku, `Agent`; worktree si hay paralelo) → el dev implementa contra los tests.
5. **Verificar** (orquestador): re-corré los tests + `measure_complexity`/`run_integration_gate`.
   FAIL → `SendMessage` al mismo dev con el error (máx 2; a la 3ª subdividí).
6. **Integrar + reportar**; suite completa 2×; commit por batch verificado.

## Diferencias clave vs pm-glm-ccdd (v1)
| | v1 (GLM/Ollama) | v2 (nativo) |
|---|---|---|
| Dev | GLM externo (`ollama launch`) | sub-agente `Agent` (Haiku) |
| Paralelo sin colisión | declarar archivos disjuntos (manual) | `isolation:"worktree"` (automático) |
| Reintento | relanzar GLM (re-envía spec) | `SendMessage` (conserva contexto) |
| Costo del dev | pool EXTERNO de GLM (fuera del presupuesto de tu sesión) | tokens Haiku EN tu sesión (medidos exactos) |
| Fragilidad | `< /dev/null`, MCP mínimo, ventanas de cuota, arranques escalonados | ninguna de esas (nativo) |
| Medición de costo | opaca (externa) | exacta (`subagent_tokens` en la notificación) |

**Trade-off honesto:** v2 gana en robustez, worktree y retries con contexto, y mide el costo con
precisión; pero el costo del dev se paga en el **presupuesto de tokens de tu sesión** (no un pool
externo). Si el dataset de tareas es enorme y GLM externo sale más barato por token, v1 puede ganar
en costo bruto; v2 gana en fiabilidad y ergonomía. Decidilo por A/B (el gate es el juez).

## Todo lo demás (idéntico a pm-glm-ccdd)
Plantilla de spec, red-team del HECHO, RECON, política de reintentos/timeouts, verify-by-artifact,
suite 2x anti-flaky, "el orquestador corre el gate", y **memoria compartida cq-git** (query en el paso 0
del PLAN; el conocimiento viaja en la spec, nunca como tools del subagente; FAIL→PASS no obvio =
candidato a KU; confirm/flag para cerrar el loop; cq no relaja el gate): ver
[pm-glm-ccdd](../pm-glm-ccdd/SKILL.md). Esta skill NO los reescribe; solo cambia el mecanismo de delegación.

## Lecciones del gate CCDD (verificado, demo en repo TypeScript)
- **Redactar el contrato formal toma varias vueltas de `lint_task_contract`**: exige, además de
  los campos obvios (`task`/`intent`/`target`/`signature`), los campos `budget`/`tests`/
  `test_command` en el frontmatter, y 7 secciones en un ORDEN CANÓNICO específico (`## Intent`,
  `## Interface`, `## Invariants`, `## Examples`, `## Do / Don't`, `## Tests`, `## Constraints` —
  Tests va DESPUÉS de Do/Don't, no antes). No lo escribas de memoria: mandá un primer intento
  mínimo y corregí contra los `findings` que devuelve; es más rápido que adivinar el formato completo.
- **`check_signature` es AST puro y asume Python**: a diferencia de `lint_task_contract` y
  `measure_complexity`, su schema NO tiene parámetro `language` — devuelve `{"mismatch": "parse error"}`
  en TS/JS/otros lenguajes. En repos no-Python, la verificación de firma dentro del paso 5 (Verificar)
  queda limitada a `lint_task_contract` (que sí valida firma "por aridad genérica" para lenguajes sin
  parser nativo) + `measure_complexity`; no uses `check_signature` como parte del veredicto fuera de Python.

## Gate sin MCP: Nivel 1 de KDD (verificado, demo con el template real)
Si el repo es un [KDD](https://github.com/MauricioPerera/KDD) instanciado (`scripts/validate_contracts.py`
+ `knowledge/contracts/` presentes), el paso 3 (contrato + lint) y el paso 5 (verificar) tienen una vía
SIN MCP, más portable que `lint_task_contract`/`measure_complexity`:
- Contrato en `knowledge/contracts/<task>.md` con el esquema completo de KDD: frontmatter OKF
  (`type`/`title`/`description`/`tags`) + campos CCDD + **`tests_sha256` obligatorio** (sellado con
  `python scripts/validate_contracts.py --hash <ruta-tests>` — congela el archivo de tests; si alguien
  lo edita después, el hash no matchea y el validador lo marca en rojo).
- Lint/veredicto: `python scripts/validate_contracts.py knowledge/contracts` + el `test_command` del
  contrato, ambos en verde. Escrito con el esquema completo desde el principio, pasó en la primera
  pasada (sin las vueltas de iteración que sí hacen falta contra `lint_task_contract`).
- Diferencia real: sin el MCP (solo Nivel 1), el `budget` del frontmatter es DECLARATIVO — el
  validador solo chequea que esté presente, no lo hace cumplir. El enforcement real de complejidad
  sigue siendo trabajo de `measure_complexity`/`run_integration_gate` (Nivel 2, con MCP). Si el MCP
  está disponible, seguí usándolo para esa parte — no es sustituible por Nivel 1 solo.
- Esto NO reemplaza el paso 4 (Delegar impl): el implementador sigue siendo un dev nativo (Haiku/Opus
  vía `Agent`), no cambia por tener KDD instanciado — el gate solo cambia CÓMO se verifica.
