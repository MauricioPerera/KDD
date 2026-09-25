# CONTRACT-25 — Registro MCP + familia `matches` — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-25-mcp-registry.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculos motor+gate (51) | ✅ verdes sin que el dev los toque (sellos `154fb9f6...` / `6fcfbbb0...`, reforzados y re-sellados por el PM ANTES de delegar) | corrida PM |
| Gate de rules | ✅ `0 error(es) en 5 archivo(s)` — dominio nuevo con REPRO verde | corrida PM |
| Mutación PM: secreto literal | ✅ REPRO divergence exacta (`expected=[], actual=['env_entries']`), exit 1 | copia mutada re-sellada |
| Mutación PM: typo `matchess` | ✅ `FAMILIA unknown key`, exit 1 | copia mutada |
| Canarios (4 goldens previos) | ✅ byte-intactos (`git diff` vacío) | corrida PM |
| 6 gates | ✅ exit 0 (17 contratos, 32 nodos, 25 specs, 5 rule-sets, 6 skills) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**315 tests**) | corridas PM |
| Post-init neutral | ✅ los 3 artefactos nuevos al MANIFEST | `test_init_project` en suite |
| Sin secretos al repo | ✅ ejemplo 100% sintético; la config real solo se OBSERVÓ en RECON | review del diff |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

**La doctrina evidencia-primero funcionando en cámara lenta.** C23 midió la clase
"propiedad de texto" en el dominio editorial y la dejó FUERA de las familias ("solo se
agregarían si otro dominio repite la clase"). El RECON de C25 sobre la config MCP real
del usuario — 5 servidores, 3 con contraseñas literales en `env` — produjo la segunda
aparición: la regla central de un registro commiteable ("secretos SOLO como referencias
`${VAR}`") es un patrón sobre strings. Segunda aparición ⇒ familia `matches`
(`{field, pattern}`, `re.search`, saltea None/no-string igual que `bounds` saltea
no-números), top-level y dentro de `each`.

**Fronteras honestas del dominio**: el servidor VIVO (handshake, tools reales, latencia)
queda `code_only` con razón — exige red, fuera del nivel 1; la unicidad de nombres queda
cerrada POR CONSTRUCCIÓN (el formato origen es un objeto keyed). Ni una regla de más.

## Verificación final del PM (independiente del dev)

- Oráculos 51/51 con sellos intactos; mutaciones propias (arriba); gates 6/6; suite 2×.
- Perímetro del dev limpio: SOLO `scripts/rule_engine.py` y `scripts/validate_rules.py`;
  sin re-delegaciones.
- Incidente de verificación del PM: la primera corrida de mutaciones dio FALSO VERDE
  (heredoc de Python con ruta POSIX de GitBash que Python-Windows no resuelve — la misma
  clase del /tmp de C15). Detectado porque la mutación no imprimió confirmación; rehecho
  pasando la ruta por `cygpath -w` + `sys.argv`, con la mutación confirmada por print
  antes de medir. Regla operativa: una mutación solo cuenta si su aplicación es
  observable.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C25-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. Con C25 quedan cubiertos los dos usos de mayor valor personal de la lista
(skills C24, MCP C25). En Unreleased acumulan C23+C24+C25 para un eventual v1.3.0.
