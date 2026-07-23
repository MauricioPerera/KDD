# Contrato 32 — Preflight: dry-run local de los 12 gates + scoping por contrato

Prerrequisitos: contratos 01-31 cerrados, HEAD `a55decd` (v1.7.0), suite 580 verde 2×, CI verde
en ambas patas. Nace de **feedback externo real de adopción** (textual): *"Would love to see a
built-in dry-run mode that shows which of the 12 gates would fail on the current contract before
any agent touches the code. Would make onboarding way smoother for teams adopting KDD and help
catch weak test seals early."* — exactamente la evidencia de demanda que la política de contratos
diferidos exige antes de construir.

RECON honesto: el motor YA existe — `mcp_gate_dispatch.run_all_level1()` (Contrato
mcp-gate-dispatch, v1.6.0) corre los 11 gates de Nivel 1 — pero **no tiene boca CLI**: solo es
invocable vía el MCP server (`pip install mcp` + registrar + cliente MCP), una barrera real para
el onboarding que el feedback describe. El "12 gates" del feedback calza con `GATE_SPECS` (12);
el 12º (`validate_attestation`) es local-only (CI no ve `.agents/logs/`), así que un dry-run
local es el ÚNICO lugar donde los 12 corren juntos: el preflight da cobertura 12/12, una más
que CI. La mitad "weak test seals" del feedback queda deliberadamente FUERA (heurísticas de
calidad de oráculo merecen su propia definición de hecho — contrato futuro si la demanda
persiste); este contrato solo detecta seal **desincronizado** en el modo `--contract`, que ya
es más temprano que esperar al gate.

> Capa: contrato de ejecución. T1 (código, dev efímero GLM) lleva su task contract en
> `knowledge/contracts/preflight.md` con oráculo congelado `tests/test_preflight.py` (autorado
> y sellado por el orquestador ANTES de delegar — el implementador nunca toca su oráculo).
> T2 (docs, dev efímero GLM) con hecho por greps. Herramienta OPT-IN, NO gate de CI de este
> repo — CI ya corre cada gate como paso propio; mismo estatus que `benchmark_gates.py`
> (existe, se prueba, no se impone). NO cambia el conteo "11 gates de Nivel 1".

Decisiones de diseño fijadas (el CÓMO interno es del dev):

- **CLI**: `python scripts/preflight.py [--repo-root DIR] [--contract NAME]`, exit 0/1.
- **Modo full**: los 12 de `ALL_GATES` (= `LEVEL1_GATES` + `validate_attestation`, derivado del
  dispatch, jamás una segunda lista hardcodeada), una línea por gate (PASS/FAIL/TIMEOUT) +
  resumen `N/12`. Reporta TODOS aunque falle el primero (diagnóstico, no short-circuit).
- **Modo `--contract`**: 3 chequeos (`frontmatter`, `seal`, `test_command`) sobre
  `knowledge/contracts/<name>.md`; seal bit-compatible con `validate_contracts.py --hash`
  (LF-normalizado); test_command con el dialecto de `validate_test_commands` (`shlex`
  `posix=False` en Windows, timeout 120s). NO corre los 12 gates.
- **El oráculo nunca corre gates reales**: runner fake + fixtures tmpdir (la recursión de
  `run_all_level1` contra el repo vivo está documentada en `knowledge/mcp-server.md`; además
  `validate_test_commands` ejecuta el `test_command` de ESTE contrato en CI con timeout 120s).

## Tareas

- **T1 (dev GLM)** — implementar `scripts/preflight.py` contra el oráculo congelado hasta
  `python -m unittest tests/test_preflight.py` verde + suite completa verde.
- **T2 (dev GLM)** — docs: mención en `knowledge/quickstart.md` (paso preflight antes de
  delegar), sección corta en `knowledge/validacion.md` (dejando claro que NO es un gate nuevo),
  cross-ref en `knowledge/mcp-server.md` (CLI vs tool MCP `run_all_level1`), entrada en
  `knowledge/index.md`, mención de una línea en `README.md`.
- **T3 (orquestador)** — CHANGELOG + `docs/reports/CONTRACT-32-REPORT.md` (el changelog gate
  exige la entrada), verificación total local (los 11 gates de CI + attestation + suite 2×
  + dogfood: `python scripts/preflight.py` sobre este mismo repo), push a `main`, CI verde
  en ambas patas.

## Criterios de aceptación

- [ ] `python -m unittest tests/test_preflight.py` verde (14/14) sin editar el oráculo; sello
  `tests_sha256` de `knowledge/contracts/preflight.md` intacto y sincronizado.
- [ ] Suite completa `python -m unittest discover -s tests -p "test_*.py"` verde 2× (dos corridas
  idénticas, salida real pegada).
- [ ] Los 11 gates de CI + `validate_attestation` verdes en local (réplica exacta de
  `.github/workflows/validate.yml`, incluidos los pasos con default hardcodeado).
- [ ] Dogfood: `python scripts/preflight.py` sobre este repo sale 0 con resumen `12/12`;
  `python scripts/preflight.py --contract preflight` sale 0 con `3/3`.
- [ ] Docs: grep con hit obligatorio de `preflight` en `knowledge/quickstart.md`,
  `knowledge/validacion.md`, `knowledge/mcp-server.md`, `knowledge/index.md` y `README.md`;
  y `validacion.md` sigue afirmando 11 gates de Nivel 1 (el preflight no altera el conteo).
- [ ] CHANGELOG con entrada enlazada a `docs/reports/CONTRACT-32-REPORT.md`
  (`validate_changelog` verde).
- [ ] CI verde en ambas patas (ubuntu + windows) tras el push.

## Restricciones

- T1: Tocar SOLO `scripts/preflight.py`. NO tocar `tests/test_preflight.py` (oráculo congelado),
  `knowledge/contracts/preflight.md` (contrato sellado), ni ningún otro archivo del repo.
- T2: Tocar SOLO `knowledge/quickstart.md`, `knowledge/validacion.md`, `knowledge/mcp-server.md`,
  `knowledge/index.md`, `README.md`. NO tocar `scripts/` ni `tests/` (otro dev trabaja ahí).
- ASCII puro en `scripts/preflight.py` (`lint_ascii` lo audita). Los nodos `knowledge/` siguen
  el registro del repo (tuteo, no voseo).
- ABORTAR SI el oráculo congelado resulta incumplible sin violar el contrato sellado, si el
  hecho exige tocar archivos fuera del perímetro declarado, o si falta una dependencia que no
  se puede instalar → PARÁ, documentá el porqué con evidencia en el REPORT y respondé
  BLOQUEADO + 1 línea. Prohibido editar el oráculo, inventar tests o debilitar un assert.
