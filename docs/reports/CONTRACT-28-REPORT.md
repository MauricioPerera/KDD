# CONTRACT-28 — Gate de perímetro — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-28-perimeter-gate.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del gate (16) | ✅ verde sin modificarlo (sello `9e36981a...`) | corrida PM |
| Oráculo de validate_contracts (47, reforzado por PM antes de delegar) | ✅ verde | corrida PM |
| 20 contratos migrados con `touch_only` | ✅ `validate_contracts` exit 0 | corrida PM |
| Dogfood: archivos del dev de ESTE contrato contra su propio perímetro | ✅ exit 0 (`3 archivo(s)`); con `README.md` inyectado → `OUT_OF_PERIMETER` nombrándolo, exit 1 | corrida PM |
| Mutación PM: contrato sin `touch_only` | ✅ `FM_KEY_touch_only`, exit 1 | copia mutada |
| Mutación PM: perímetro cubriendo el oráculo (`tests/*`) | ✅ `FM_TOUCH_TESTS` "oraculo protegido", exit 1 | copia mutada |
| Coherencia de parsers a 4 vías | ✅ (vc ↔ vok ↔ vs ↔ vp) | corrida PM |
| 7 gates | ✅ exit 0 (20 contratos, 36 nodos, 28 specs, 6 rule-sets, 6 skills, 28 changelog) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**374 tests**) | corridas PM |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

**"Tocar SOLO" dejó de ser prosa.** Idea importada del análisis de Shepherd
(shepherd-agents, arXiv 2605.10913 — la firma como superficie de permisos), traducida al
nivel de KDD: verificación post-hoc del diff en vez de jail de syscalls. La evidencia era
propia: el PM verificó perímetros A MANO en C24, C25, C26 y C27 — práctica manual
repetida ⇒ gate, por doctrina.

Dos piezas que se cierran mutuamente con el sello existente:
- **`touch_only` obligatoria** en el frontmatter (precedente C12): el perímetro como
  DATO, con `validate_contracts` exigiendo que el `target` esté cubierto y que el
  oráculo (`tests`) quede FUERA — salvo el caso real `tests == target` (2 contratos
  cuyo entregable ES un test), medido en RECON y resuelto en diseño, no parcheado.
- **`validate_perimeter.py`**: el PM pipea `git diff --name-only` y cualquier archivo
  del dev fuera del perímetro rompe con `OUT_OF_PERIMETER`; tocar el oráculo rompe con
  `TESTS_TOUCHED`. La pinza completa: el dev no puede editar los tests (sello sha256)
  ni salirse de su zona (perímetro) — y ya no depende de la disciplina del PM.

**Alcance honesto**: el gate NO es paso de CI del repo — un commit mergeado mezcla
legítimamente archivos del PM con los del dev; el diff del dev existe solo en el momento
de la verificación, y ahí corta. La cobertura de CI viene por los checks estructurales
en `validate_contracts` (paso existente) y por el oráculo sellado del gate en la suite.

## Verificación final del PM (independiente del dev)

- Oráculos 16/16 + 47/47 con sello intacto; mutaciones observables matadas; dogfood
  sobre el diff real de este mismo contrato; gates 7/7; suite 2× 374/374.
- Perímetro del dev limpio: SOLO `scripts/validate_perimeter.py`,
  `scripts/validate_contracts.py` (checks solo-agregar) y
  `tests/test_parser_coherence.py` (extensión a 4 vías); sin re-delegaciones.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C28-REPORT.md`.

## Pendientes / ítems de seguimiento

- La skill `pm-native-ccdd` puede ganar el paso "correr validate_perimeter sobre el
  diff del dev" como parte del cierre estándar (activo operativo del usuario — se
  toca solo con su doctrina de sincronía, fuera de este contrato).
