# CONTRACT-02 — El ensamblador de contexto como paso estándar de las reglas de agentes — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-02-agents-context.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Validador de contratos | ✅ exit 0 (3 contratos) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**41 tests**: 38 + 3 de coherencia) | corridas PM idénticas |
| Test de coherencia no decorativo | ✅ mutación (quitar la regla de AGENTS.md) → test rojo nombrando la referencia y el archivo; restaurar → verde | mutación ejecutada por el dev Y reproducida por el PM |
| Puentes raíz intactos | ✅ `AGENTS.md`/`CLAUDE.md` de raíz sin cambios | git status |

## Entregado (`9133ccc`, implementado por agente efímero contra el task contract)

- `.agents/AGENTS.md` — regla **7. Contexto presupuestado (CCDD Nivel 2)**: ensamblar el
  contexto de toda tarea delegada con `python scripts/assemble_context.py ccdd/context.json
  "<tarea>"`; el reporte de slots/guardrails es parte de la evidencia en
  `.agents/logs/<task>-REPORT.md`; guardrail `on_fail: abort` bloquea la tarea.
- `.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md` — sección **7** integrando el paso de
  ensamblado en el flujo de definición/delegación, sin duplicar la regla.
- `tests/test_agents_rules.py` — 3 tests de coherencia que fijan regla ↔ herramienta:
  referencias literales a `scripts/assemble_context.py` y `ccdd/context.json` en ambos
  documentos + existencia de los archivos referenciados. Renombrar la herramienta sin
  actualizar las reglas pone la suite (y el CI) en rojo.

Task contract: `knowledge/contracts/agents-context-rule.md` (validador exit 0). Evidencia
de tarea del agente: `.agents/logs/agents-context-rule-REPORT.md` (local, gitignorada).

## Verificación final del PM (independiente del agente)

- Validador + suite 2× (41/41 ambas) ejecutados por el PM.
- Prueba de mutación reproducida por el PM: `grep -v assemble_context` sobre AGENTS.md →
  `unittest` exit 1 con mensaje que nombra la referencia faltante; restauración → exit 0.

## Pendientes / ítems de seguimiento

Ninguno. La plantilla queda completa: KB OKF + contratos 2 capas + validador + ensamblador
de contexto + reglas de agentes ancladas por test.
