# Contrato 33 — Auditor de seals débiles: el sello garantiza integridad, no fuerza

Prerrequisitos: contratos 01-32 cerrados, HEAD `48197db` (v1.8.0), suite 594 verde 2×, CI verde
en ambas patas. Cierra la **mitad diferida del mismo feedback externo** que originó el C32
(*"help catch weak test seals early"*) — diferida entonces con porqué documentado en el spec del
C32, ejecutada ahora por pedido directo del usuario. La evidencia de demanda es la misma cita.

RECON honesto: `tests_sha256` congela el oráculo pero no mide su fuerza — un tests file vacío,
sin asserts reales o que jamás menciona al target pasa `validate_contracts` verde. Prototipo de
las heurísticas corrido contra el repo vivo ANTES de congelar el oráculo: 30 contratos, **2
hallazgos aparentes que resultaron falsos positivos** — `agents-context-rule` y
`versioning-plantilla` son contratos de coherencia **auto-referenciales** (`target == tests`: el
archivo de tests ES el entregable) y un archivo se cubre a sí mismo trivialmente. La regla quedó
incorporada a la semántica congelada: con `target == tests`, `WEAK_TARGET_UNREFERENCED` se
omite. Baseline resultante del repo vivo: **0 findings / 31 auditados** (30 al momento del prototipo + el propio seal-audit) — ese es el dogfood.

**Frontera mecánico/juicio (la tesis del contrato):** detectar la AUSENCIA (cero asserts
no-constantes, cero funciones de test, target jamás referenciado) es mecánico y va en el
auditor. Juzgar la CALIDAD de un assert existente es mutation testing (`mutation_audit` del MCP
ccdd-complexity) y queda FUERA. Por eso es **advisory**: warnings + exit 0 por default;
`--strict` (exit 1 con findings) para el equipo que elija imponerlo.

> Capa: contrato de ejecución. T1 (código, dev efímero GLM) lleva su task contract en
> `knowledge/contracts/seal-audit.md` con oráculo congelado `tests/test_audit_seals.py`
> (autorado y sellado por el orquestador ANTES de delegar). T2 (docs, dev efímero GLM) con
> hecho por greps. Herramienta OPT-IN — NO gate de CI, NO entra en `GATE_SPECS` (eso engordaría
> `LEVEL1_GATES` y rompería el oráculo congelado del preflight, que fija 12 gates exactos);
> mismo estatus que `benchmark_gates.py`/`preflight.py`.

Decisiones de diseño fijadas (el CÓMO interno es del dev):
- CLI: `python scripts/audit_seals.py [contracts_dir] [--repo-root DIR] [--strict]`.
- Reglas: `WEAK_TESTS_MISSING/EMPTY/UNPARSEABLE/NO_TEST_FUNCTIONS/NO_ASSERTS/TARGET_UNREFERENCED`.
- Detección por `ast` (stdlib), nunca regex sobre código; `assert True` no cuenta;
  `self.assert*` sí; tests no-Python (`.js` de example-node-greet) solo reciben los chequeos
  textuales; MISSING/EMPTY/UNPARSEABLE cortocircuitan.
- `forbids: ['network', 'subprocess', 'llm']` — solo lee archivos, más estricto que preflight.

## Tareas

- **T1 (dev GLM)** — implementar `scripts/audit_seals.py` contra el oráculo congelado hasta
  `python -m unittest tests/test_audit_seals.py` verde + suite completa verde.
- **T2 (dev GLM)** — docs: sección en `knowledge/validacion.md` (advisory, NO gate; junto a la
  del preflight), entrada en `knowledge/index.md`, mención de una línea en `README.md`.
- **T3 (orquestador)** — CHANGELOG + `docs/reports/CONTRACT-33-REPORT.md`, verificación total
  local (11 gates CI + attestation + suite 2× + dogfood `audit_seals` sobre este repo = 0
  findings/31 + preflight 12/12 intacto), push a `main`, CI ambas patas.

## Criterios de aceptación

- [ ] `python -m unittest tests/test_audit_seals.py` verde (15/15) sin editar el oráculo; sello
  `tests_sha256` de `knowledge/contracts/seal-audit.md` intacto.
- [ ] Suite completa `python -m unittest discover -s tests -p "test_*.py"` verde 2×.
- [ ] Los 11 gates de CI + `validate_attestation` verdes en local.
- [ ] Dogfood: `python scripts/audit_seals.py` sobre este repo → 0 findings, 31 auditados,
  exit 0; y `python scripts/audit_seals.py knowledge/contracts --strict` → exit 0.
- [ ] El preflight NO se rompió: `python scripts/preflight.py --contract seal-audit` → 3/3
  exit 0, y su oráculo `python -m unittest tests/test_preflight.py` sigue verde (12 gates).
- [ ] Docs: `grep -n "audit_seals" knowledge/validacion.md knowledge/index.md README.md` → hit
  en los 3; `validacion.md` sigue afirmando 11 gates de Nivel 1.
- [ ] CHANGELOG con entrada enlazada a `docs/reports/CONTRACT-33-REPORT.md`
  (`validate_changelog` verde).
- [ ] CI verde en ambas patas tras el push.

## Restricciones

- T1: Tocar SOLO `scripts/audit_seals.py`. NO tocar `tests/test_audit_seals.py` (oráculo
  congelado), `knowledge/contracts/seal-audit.md` (sellado), `scripts/preflight.py`,
  `scripts/mcp_gate_dispatch.py`, ni ningún otro archivo.
- T2: Tocar SOLO `knowledge/validacion.md`, `knowledge/index.md`, `README.md`. NO tocar
  `scripts/` ni `tests/` (otro dev trabaja ahí).
- ASCII puro en `scripts/audit_seals.py` (`lint_ascii`). Registro de los nodos: tuteo.
- ABORTAR SI el oráculo congelado resulta incumplible sin violar el contrato sellado, si el
  hecho exige tocar archivos fuera del perímetro, o si falta una dependencia no instalable →
  PARÁ, documentá con evidencia en el REPORT y respondé BLOQUEADO + 1 línea. Prohibido editar
  el oráculo, inventar tests o debilitar asserts.
