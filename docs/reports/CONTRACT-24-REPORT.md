# CONTRACT-24 — Gate de skills — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-24-skills-gate.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del gate (26) | ✅ verde sin modificarlo (sello `35f2a4a4...`) | corrida PM |
| Gate sobre activos REALES | ✅ `0 error(es) en 6 skill(s)`, exit 0 | corrida PM |
| Byte-identidad operativa↔repo | ✅ 5/5 IDENTICA (diff vacío) | corrida PM |
| Mutación PM: enlace roto | ✅ exit 1 nombrando `../no-existe/SKILL.md` (×3) | copia mutada |
| Mutación PM: name duplicado | ✅ exit 1 con `NAME_DUP` anclado en el archivo posterior | copia mutada |
| Coherencia de parsers a 3 vías | ✅ `test_parser_coherence` OK (vc ↔ vok ↔ vs) | corrida PM |
| 5 gates previos | ✅ exit 0 (17 contratos, 31 nodos, 24 specs, 4 rule-sets) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**305 tests**) | corridas PM |
| CI (7º paso nuevo) | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

Primer gate que custodia **activos reales del repo** en vez de ejemplos: las skills de
agente (`skills/` versionadas + `.agents/skills/`). Checks: `SKILL.md` presente,
frontmatter parseable, `name` kebab-case == directorio y único entre dirs, `description`
en [50, 1024] (cotas informadas por los datos reales: 400-780), cuerpo no vacío, y
enlaces relativos que resuelven (con stripping de code spans/fences, como `validate_okf`).
Capa opcional: dir ausente pasa con INFO.

**El RECON pagó antes de que el gate existiera**: encontró 3 enlaces rotos REALES en las
copias vivas (`delegar-glm-ccdd` ×2 y `pm-glm-ccdd` ×1 apuntando a un sibling inexistente;
más un ejemplo ilustrativo sin backticks en la skill híbrida). Reparados respetando la
doctrina de sincronía: fix en `~/.claude/skills/` PRIMERO (URL canónica del repo), copia
byte-idéntica después; el ilustrativo pasó a code span. La byte-identidad quedó como
CRITERIO verificado por diff, no como promesa.

El dialecto mini-YAML ahora está fijado a **3 vías** por `test_parser_coherence`
(validate_contracts ↔ validate_okf ↔ validate_skills): una edición a cualquiera de las
tres copias que divergiera el dialecto rompe la suite.

## Verificación final del PM (independiente del dev)

- Oráculo 26/26; sello intacto; mutaciones propias (arriba); gates 6/6; suite 2× 305/305.
- Perímetro limpio: el dev tocó SOLO `scripts/validate_skills.py` y
  `tests/test_parser_coherence.py` (extensión, sin debilitar).
- **1 re-delegación**: el Resumen del CLI contaba skills desde los findings — con activos
  limpios decía "0 skill(s)" tras validar 6 (misma clase de deshonestidad que C18). El
  oráculo fue REFORZADO y RE-SELLADO primero (`test_cli_resumen_counts_scanned_skills`),
  después se re-delegó el fix. El propio gate OKF también atrapó al PM: el contrato nuevo
  nació sin `title/description/tags` y `validate_okf` lo rechazó antes del commit.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C24-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. Candidato futuro anotado en el spec-log de la sesión: contratos de servidores
MCP (el otro uso de alto valor personal de la lista).
