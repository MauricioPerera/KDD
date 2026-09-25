# CONTRACT-30 — Gate de UX/accesibilidad — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-30-ux-page-gate.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo (39) | ✅ verde sin modificarlo (sello `aa4929a4...`); `TestRepoReal` deja de saltearse y pasa contra el ejemplo real | corrida PM |
| Ejemplo real (`examples/ux-page/demo.html`) | ✅ `python scripts/validate_ux_page.py examples/ux-page` → `0 error(es), 0 warning(s)`, exit 0 | corrida PM |
| Mutaciones PM (fixtures propias, no del dev) | ✅ contraste real bajo → `CONTRAST_LOW` WARNING sin bloquear exit; id inventado por el PM → `ID_UNRESOLVED` ERROR; página con solo WARNING → exit 0 confirmado | corridas PM |
| 8 gates | ✅ exit 0 (22 contratos, 39 nodos, 30 specs, 6 rule-sets, 6 skills, 30 changelog, 1 página UX) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**433 tests**) | corridas PM |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

Octavo gate de nivel 1 (capa opcional), y el segundo en esta racha diseñado leyendo primero
a un tercero real de producción antes de construir: `google-labs-code/design.md` (25k
stars, 2k forks). Dos calibraciones concretas que llegaron de esa lectura, ambas fijadas en
el spec ANTES de delegar:

1. **Contraste sobre datos estructurados, no CSS libre** — un bloque
   `<script type="application/json" id="ux-contrast-pairs">` con pares `{scope, text, bg}`
   explícitos, igual que su `components: {backgroundColor, textColor}`. La fórmula de
   luminancia relativa WCAG se verificó independientemente contra `color-parser.ts` de
   design.md: coinciden exactamente.
2. **Severidad calibrada, no implícita** — `CONTRAST_LOW`/`MOTION_UNGUARDED` son WARNING
   (no bloquean el exit code), `HTML_UNCLOSED`/`I18N_*`/`ID_UNRESOLVED` son ERROR (el
   equivalente exacto de su `broken-ref`). Coincide con la calibración real de un linter
   con adopción masiva, no con una intuición propia.

**Misma frontera mecánico/juicio que C23 (editorial)**: lo que exige un navegador real
(overflow en anchos con nombre, si un `position:sticky` queda pegado en todo el rango de
scroll — el bug real que el PM encontró construyendo el propio landing page de KDD esta
sesión, errores de consola, `:focus-visible` renderizado) queda declarado FUERA, no
fingido con una aproximación estática débil. Si el diseño es lindo o la paleta es la
correcta: juicio humano, nunca de este gate.

**Honestidad de alcance**: el landing page real de KDD (construido en esta misma sesión,
aún en el scratchpad) queda deliberadamente FUERA del perímetro de este contrato — la
decisión de publicarlo a GitHub Pages sigue pendiente y separada. El ejemplo que sí se
commiteó es mínimo y proporcional (`examples/ux-page/demo.html`), como el resto de
`examples/`.

## Verificación final del PM (independiente del dev)

- Oráculo 39/39 con sello intacto; `TestRepoReal` verificado sin skip contra el ejemplo
  real; mutaciones con fixtures propias del PM (nunca las del dev) incluyendo un
  descubrimiento colateral no accionable (los tokens `--ink-panel`/`--panel-2` del
  landing page real fallan WCAG 1.12:1 — fuera de alcance de este contrato, anotado
  para cuando se retome esa decisión); 8 gates; suite 2× 433/433.
- Perímetro del dev limpio: SOLO `scripts/validate_ux_page.py`; sin re-delegaciones.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C30-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno propio de este contrato. Sigue pendiente, y sigue siendo decisión separada del
usuario: publicar el landing page de KDD a GitHub Pages (y, si se hace, corregir el
contraste de sus tokens dark antes).
