# CONTRACT-04 — Dogfood E2E: una feature real por el ciclo KDD completo — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-04-dogfood-e2e.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Tests congelados (20) | ✅ verdes SIN modificación del oráculo (146 líneas, hash verificado por el PM) | corrida PM |
| Suite completa | ✅ verde 2× (**80 tests**: 60 + 20) | corridas PM idénticas |
| Validadores (contratos + OKF) | ✅ exit 0 ambos (5 contratos, 10 nodos) | corrida PM |
| Regla 7 (contexto ensamblado) | ✅ reporte de slots del ensamblador en la evidencia del agente | `.agents/logs/validate-user-record-REPORT.md` |
| Perímetro del implementador | ✅ tocó SOLO `src/users.py` | git status |

## El caso resuelto (referencia para quien clone la plantilla)

Este contrato ejecutó el ciclo KDD completo, con cada rol en su lugar:

1. **Orquestador** (`0cbf520`): autoró el task contract
   [`validate-user-record.md`](../../knowledge/contracts/validate-user-record.md) —
   anclado por enlace al nodo [`users_table.md`](../../knowledge/data_models/users_table.md)
   (las reglas de dominio viven en la KB, el contrato no las duplica) — y el **oráculo
   congelado** `tests/test_users.py` (20 tests que fijan mensajes, conteos de violaciones
   y robustez), ANTES de delegar. El implementador nunca escribe ni modifica su propio
   oráculo.
2. **Agente efímero** (`5ab9e13`): ensambló su contexto (regla 7, C02) con
   `assemble_context.py`, leyó contrato + modelo + oráculo, e implementó SOLO
   `src/users.py` (`validate_user_record`: pura, acumula todas las violaciones, nombra el
   campo en cada mensaje, nunca lanza) hasta poner el oráculo en verde.
3. **Gates nivel 1**: validador de contratos + validador OKF (C03) + suite `unittest` —
   los tres en CI.
4. **Verificación del orquestador**: oráculo intacto (conteo de líneas + hash), suite 2×,
   validadores, perímetro por `git status`. Evidencia del agente en `.agents/logs/`
   (local, gitignorada); este reporte es la evidencia publicada.

Diferencia deliberada con C01-C03 (tooling): en features de producto el oráculo lo autora
el orquestador y queda congelado pre-delegación — CCDD canónico.

## Pendientes / ítems de seguimiento

Ninguno. La plantilla queda con su ciclo completo demostrado de punta a punta sobre una
feature real.
