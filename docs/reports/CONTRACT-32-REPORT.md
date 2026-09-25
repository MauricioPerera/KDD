# CONTRACT-32 — Preflight: dry-run local de los 12 gates — REPORT

Fecha: 2026-07-17
Spec: `specs/CONTRACT-32-preflight.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo (14) | ✅ verde sin modificarlo, sello `cc30ac4b...` intacto tras la implementación (re-hasheado por el PM) | corrida PM |
| Perímetro T1 | ✅ el dev de código tocó SOLO `scripts/preflight.py` | `git status` PM |
| Perímetro T2 | ✅ el dev de docs tocó SOLO sus 5 archivos declarados | `git status` PM |
| Greps de docs | ✅ `preflight` presente en quickstart, validacion, mcp-server, index y README; `validacion.md` sigue afirmando **11 gates** de Nivel 1 (el conteo no cambió) | greps re-corridos por el PM |
| Dogfood modo full | ✅ `python scripts/preflight.py` sobre este mismo repo → 12 líneas PASS + `Summary: 12/12`, exit 0 | corrida PM |
| Dogfood modo `--contract` | ✅ `python scripts/preflight.py --contract preflight` → `frontmatter/seal/test_command` PASS + `Summary: 3/3`, exit 0 | corrida PM |
| 11 gates de CI + attestation | ✅ réplica local exacta de `validate.yml`: 12/12 exit 0 (incluye `validate_test_commands`, que ejecuta el `test_command` de este contrato) | corridas PM |
| Suite `unittest` | ✅ verde 2× (**594 tests**, exit 0 ambas pasadas, +14 del oráculo nuevo) | corridas PM |
| Sin paso de CI nuevo | ✅ `preflight` no aparece en `.github/workflows/validate.yml` ni en el `GATES` de `benchmark_gates.py`, tal como exigía el contrato | greps PM |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

Primer contrato nacido de **feedback externo de adopción** (textual en el spec): pedían un
dry-run que muestre qué gates fallarían antes de que un agente toque el código. RECON honesto
primero: el motor ya existía (`mcp_gate_dispatch.run_all_level1`, C-mcp-gate-dispatch) pero solo
era invocable vía MCP; este contrato le puso la boca CLI de cero dependencias. Bonus estructural:
el preflight es el único lugar donde los **12** gates corren juntos (CI corre 11;
`validate_attestation` es local-only). La mitad "weak test seals" del feedback quedó
deliberadamente fuera con su porqué documentado en el spec (heurísticas de calidad de oráculo =
contrato futuro); el modo `--contract` ya detecta el seal desincronizado más temprano que el gate.

Proceso: oráculo congelado autorado y sellado por el orquestador ANTES de delegar; T1 (código) y
T2 (docs) corrieron como devs GLM efímeros EN PARALELO con perímetros disjuntos, ambos LISTO a la
primera, cero re-delegaciones. T1 declaró en su REPORT un bug propio hallado y corregido contra el
oráculo en su primera corrida (claves de frontmatter vs nombres de chequeo) — el oráculo haciendo
su trabajo durante la implementación, no después.

## Trade-offs y notas

- `preflight.py` reutiliza `parse_frontmatter` de `validate_contracts` y deriva `ALL_GATES` del
  dispatch: cero listas duplicadas; un gate nuevo en `GATE_SPECS` aparece en el preflight sin
  tocarlo.
- El modo full sobre este repo tarda lo que tarde `validate_test_commands` (ejecuta el
  `test_command` de los 30 contratos); es el costo inherente del dry-run completo, no un defecto
  del preflight.
- Los REPORT de los devs (`PREFLIGHT-T1/T2-REPORT.md`) quedan como evidencia local (no
  versionados), consistente con `.agents/logs/`.
