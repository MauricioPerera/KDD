# Changelog

All notable changes to the KDD Template are documented here.

## Unreleased

**Contract 19 — Second domain: border control (generality proven)** ([C19-REPORT](docs/reports/CONTRACT-19-REPORT.md))
- The papers-please vocabulary (game-protocol) expressed as pure data over the existing engine and gate: zero code for a new domain (node + rule-set + sealed golden). Second measured boundary, same class as the first: cross-field equality (`require-field-match`) stays `code_only`, matching game-protocol's own data/logic split.

**Contract 18 — Rule-contracts gate** ([C18-REPORT](docs/reports/CONTRACT-18-REPORT.md))
- The rule-contract layer now defends itself: `scripts/validate_rules.py` (level-1 gate + CI step, dual-OS) checks known families (a typo is an ERROR, not a silently ignored rule), a mandatory hash-sealed golden (`golden: {path, sha256}`, sealed with the existing `--hash`), documented `code_only` reasons, and REPRODUCTION: the declarative engine is re-run over every golden case (a valid seal with broken semantics still fails). Optional layer: projects without rule contracts pass with INFO.

**Contract 17 — Rule contract: business rules as declarative data** ([C17-REPORT](docs/reports/CONTRACT-17-REPORT.md))
- New vertiente (lineage: `game-protocol` profiles): a deterministic rule engine (`scripts/rule_engine.py`) that validates business rules expressed as declarative DATA (`required/type/enums/bounds/refs/keyed_*`), no LLM. Falsifiable experiment on the payment domain: the declarative rule-set reproduces the C16 code validator's verdicts over a frozen golden set, with exactly one documented `code_only` boundary (exact-`True` KYC, since Python value-equality treats `1 == True`). Engine + format node are infra; the payment rule-set/golden are EXAMPLE artifacts.

**Contract 16 — Example domain: per-country payment validation** ([C16-REPORT](docs/reports/CONTRACT-16-REPORT.md))
- Resolved example of financial-domain frozen contracts: `validate_payment_limit` (per-country limit + beneficiary verification) as a pure function, with its frozen oracle and a data-model node holding the compliance rules. Added as an EXAMPLE artifact (removed by `init_project` on instantiation), so the template stays domain-neutral.

## v1.0.0 — 2026-07-07

### What's included

The Knowledge-Driven Development (KDD) template is now complete and operationally proven:
- **OKF Knowledge Base:** Open Knowledge Format specification, validatable by machine, with indexing and cross-referencing.
- **CCDD Contracts (2 layers):** Execution contracts (project-level) and task contracts (developer-level) with deterministic gates and frozen test oracles.
- **Deterministic Context Assembler:** Token-budgeted, retriever-based assembly of knowledge for agent delegations.
- **3 Validation Gates:** Contract validator (specs + task contracts) + OKF validator (KB structure) + CI with cross-platform suite (2× run).
- **Dogfood Cycle Complete:** Full KDD methodology demonstrated end-to-end on real features, from contract authorship to agent execution to PM verification.
- **Upgrade Path:** Manual documented procedure for bringing improvements from upstream template releases.

### History by contract

**Contract 01 — Completar la plantilla KDD** ([C01-REPORT](docs/reports/CONTRACT-01-REPORT.md))
- Ensamblador de contexto determinista con presupuesto de tokens y compaction adaptativo.

**Contract 02 — Agentes: contexto ensamblado como paso obligatorio** ([C02-REPORT](docs/reports/CONTRACT-02-REPORT.md))
- Regla 7 de agentes: ensamblador presupuestado como paso mandatorio de toda delegación.

**Contract 03 — Validador OKF: spec en máquina** ([C03-REPORT](docs/reports/CONTRACT-03-REPORT.md))
- Validador OKF que asegura conformidad de nodos con frontmatter, tipos, enlaces y alcanzabilidad.

**Contract 04 — Dogfood E2E: ciclo CCDD completo en feature real** ([C04-REPORT](docs/reports/CONTRACT-04-REPORT.md))
- Demostración end-to-end: oráculo congelado, contrato, agente efímero, gates, verificación del PM.

**Contract 05 — Gate CCDD nivel 2 real** ([C05-REPORT](docs/reports/CONTRACT-05-REPORT.md))
- Export de contratos nativo + validación CCDD contra presupuesto de complejidad ciclomática y anidamiento.

**Contract 06 — init_project: instanciar en proyecto real** ([C06-REPORT](docs/reports/CONTRACT-06-REPORT.md))
- Script init_project con dry-run y apply todo-o-nada; clon fresco validado y operativo.

**Contract 07 — Correcciones del audit externo** ([C07-REPORT](docs/reports/CONTRACT-07-REPORT.md))
- Auditoría procesada: OKF-links, contexto honesto con regex real, export independiente de cwd.

**Contract 08 — Export cross-drive: fallo honesto** ([C08-REPORT](docs/reports/CONTRACT-08-REPORT.md))
- Detección explícita de cross-drive en Windows; mensajes de I/O precisos, no "contrato inválido".

**Contract 09 — Validador de specs: cierre/apertura** ([C09-REPORT](docs/reports/CONTRACT-09-REPORT.md))
- Validador de contratos de ejecución; ABORTAR SI y Tocar SOLO obligatorios en contratos abiertos.

**Contract 10 — Endurecer nivel 1: oráculos congelados y rutas reales** ([C10-REPORT](docs/reports/CONTRACT-10-REPORT.md))
- Oráculos congelados por sha256; rutas de target y tests exigidas existentes; placeholders reales detectados.

**Contract 11 — CI: matriz Windows y suite 2×** ([C11-REPORT](docs/reports/CONTRACT-11-REPORT.md))
- CI con matriz Windows/Linux; suite corrida 2× idéntica en ambas patas.

**Contract 12 — tests_sha256 obligatoria** ([C12-REPORT](docs/reports/CONTRACT-12-REPORT.md))
- Hash de oráculos obligatorio; helper --hash para sellar; doctrina de honestidad en documentación.

**Contract 13 — Lint ASCII de scripts** ([C13-REPORT](docs/reports/CONTRACT-13-REPORT.md))
- Linter ASCII de literales en scripts; pragma de línea y skip-file; orden determinista por (archivo, línea).

**Contract 14 — Versionado de la plantilla** ([C14-REPORT](docs/reports/CONTRACT-14-REPORT.md))
- Este CHANGELOG, el nodo de upgrade (`knowledge/plantilla-upgrade.md`), la subsección de versionado del README y el test de coherencia que los fija; primer tag `v1.0.0`.

**Contract 15 — Ensamblador a escala** ([C15-REPORT](docs/reports/CONTRACT-15-REPORT.md))
- Retriever con ranking determinista (mención > tag); corte por nodo en vez de sobre la concatenación; reporte honesto (`selected`/`cut`/`omitted_nodes`); `budget.chars_per_token` configurable.
