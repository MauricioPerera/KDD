# Changelog

All notable changes to the KDD Template are documented here.

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
