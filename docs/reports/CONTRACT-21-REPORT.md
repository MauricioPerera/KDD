# CONTRACT-21 — Ejemplo didáctico: router de mensajes — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-21-message-router.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del router (9) | ✅ verde sin modificarlo (sello `58536df6...`) | corrida PM |
| Gate sobre los 4 dominios | ✅ `0 error(es) en 4 archivo(s)` (3 previos byte-intactos + auditoría de ruteos) | corrida PM |
| **Coherencia entre formas** | ✅ toda decisión del código pasa limpia la auditoría declarativa (4 emisores probados) | verificación cruzada del PM |
| Adversarial (tabla propia del PM) | ✅ listado/else/ausente/pureza exactos | fixtures del PM |
| Mutación: golden de auditoría aflojado + re-sellado | ✅ `REPRO` | mutación PM sobre copia |
| Validadores + lint | ✅ exit 0 (14 contratos, 27 nodos, 21 specs) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**248 tests**) | corridas PM |
| Post-init neutral | ✅ los 6 artefactos del ejemplo al MANIFEST | `test_init_project` en suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra (el patrón "evento → decisión" contratado)

La pregunta "¿puedo contratar: si llega un mensaje y el emisor es Y ejecutá A, si no B?"
quedó respondida con un ejemplo mínimo en las DOS formas, sobre el MISMO dominio:

1. **La decisión como código** (`route_message`, dev efímero, cyclomatic 2): el oráculo
   congelado fija los bordes que suelen vivir implícitos — normalización de mayúsculas,
   emisor ausente/no-string → default, tabla vacía, pureza por argumento, nunca lanza. La
   rama `else` abierta es trivial en código.
2. **La auditoría como datos** (`routing-audit.rules.json`, `keyed_enums`): valida
   decisiones YA tomadas contra la política, con el gate determinista. Independiente del
   código (validó en verde ANTES de que el dev implementara).

**La frontera, ejercitada y no solo declarada**: "cualquier emisor NO listado debe haber
ido a B" es un condicional con default sobre mundo abierto — invisible para `keyed_enums`
(se salta si la clave no resuelve, semántica congelada desde C17). El golden incluye el
caso que el declarativo no ve (`code_only_miss`) y el rule-set documenta la razón. Cuarta
aparición de la clase "condicional/comparación no uniforme" en el mapa de fronteras.

**Lo que el contrato NO cubre, dicho explícito**: que el evento dispare en producción y
que A se ejecute de verdad — eso es estructura del workflow (dominio C20) + observabilidad,
no gate pre-merge.

## Verificación final del PM (independiente del dev)

- Oráculo 9/9; gate 4/4; equivalencia cruzada código↔auditoría en verde.
- Adversarial con tabla propia (no la del oráculo); mutación REPRO con sello válido.
- Validadores + lint exit 0; suite 2× consecutivas 248/248.
- Perímetro limpio (el dev tocó solo `src/route_message.py`); sin re-delegaciones.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C21-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. El ejemplo queda como la respuesta canónica y mínima al patrón evento→decisión.
