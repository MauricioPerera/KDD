# CONTRACT-31 — Gate de formato de mensaje de commit — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-31-commit-message-gate.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo (27) | ✅ verde sin modificarlo (sello `7ad8d52b...`), intacto tras el retoque del PM | corrida PM |
| Retoque trivial del PM | ✅ mensajes de finding traducidos a español (consistencia con el resto del repo) + un rule name mal etiquetado en un edge-case sin cobertura de oráculo (`--file` inexistente ahora es `MESSAGE_FILE_MISSING`, no `CONFIG_MISSING`) | corrida PM, oráculo re-verificado sin cambios |
| Mutaciones PM (fixtures propias, no del dev) | ✅ mi propio patrón informal de commit (`C31: ...`) es gramaticalmente válido pero con tipo no reconocido → `TYPE_UNKNOWN`, no `HEADER_MALFORMED` (hallazgo correcto); breaking marcado con `!` no se verifica (no exigido); scope con paréntesis anidados no matchea (edge case entendido, no bloqueante) | corridas PM |
| Dogfood real | ✅ `validate_commit_message.py examples/git/commit-convention.json --message "feat(gate): ..."` → exit 0 | corrida PM |
| Sin paso de CI nuevo | ✅ `validate_commit_message` no aparece en `.github/workflows/validate.yml` (grep = 0), tal como exigía el spec | corrida PM |
| 8 gates de CI | ✅ exit 0 (23 contratos, 41 nodos, 31 specs, 6 rule-sets, 6 skills, 30 changelog, 1 página UX) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**460 tests**) | corridas PM |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

Respuesta a la pregunta directa del usuario sobre contratos para git (issues, PRs,
commits), acotada deliberadamente a UNA sola cosa limpia: formato de mensaje de commit.
Misma disciplina evidencia-primero que C28/C30: calibrado contra un estándar público real
(Conventional Commits v1.0.0) y un linter de referencia (`commitlint`), no contra reglas
inventadas. Severidad: solo lo que rompe herramientas que dependen de la gramática del
header (`HEADER_MALFORMED`, `TYPE_UNKNOWN`, `SCOPE_REQUIRED`, `BLANK_LINE_MISSING`) es
ERROR; lo estilístico (`SUBJECT_TOO_LONG`, `SUBJECT_TRAILING_PERIOD`) es WARNING.

**Honestidad de alcance, verificada dos veces**: (1) el propio historial de KDD (`C31: ...`,
`release: ...`) NO sigue esta convención — confirmado en vivo por la mutación 1, que corrió
el mensaje REAL de este mismo commit contra el ejemplo y obtuvo `TYPE_UNKNOWN` (el tipo
"C31" no es un tipo reconocido) — así que la herramienta deliberadamente NO se volvió gate
de CI de este repo. (2) "Plantillas de PR/issue" y "verificar-y-mergear" quedaron
explícitamente fuera: lo segundo ya existe sin nombre nuevo (CI ambas patas + rama
protegida en `ccdd-gate`), documentado por referencia cruzada, no reconstruido.

## Verificación final del PM (independiente del dev)

- Oráculo 27/27 con sello intacto, incluso después de un retoque trivial de integración
  (traducción de mensajes + una corrección de rule name en un edge-case sin cobertura de
  test) — el retoque no tocó ninguna aserción del oráculo, solo texto descriptivo.
- Mutaciones con fixtures propias del PM (nunca las del dev), incluyendo el mensaje REAL
  de este commit contra la convención de ejemplo — confirmando en vivo la honestidad de
  alcance del spec.
- Perímetro del dev limpio: SOLO `scripts/validate_commit_message.py`; sin
  re-delegaciones.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C31-REPORT.md`.

## Pendientes / ítems de seguimiento

Plantillas de PR/issue (`.github/PULL_REQUEST_TEMPLATE.md`, `ISSUE_TEMPLATE/`) quedan
como candidato futuro explícito — sin evidencia hoy (cero plantillas reales en este repo
para calibrar contra ellas).
