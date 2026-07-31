# KDD Template (Knowledge-Driven Development)

[![validate-contracts](https://github.com/MauricioPerera/KDD/actions/workflows/validate.yml/badge.svg)](https://github.com/MauricioPerera/KDD/actions/workflows/validate.yml)

<a href="https://www.producthunt.com/products/kdd-knowledge-driven-development?embed=true&utm_source=badge-featured&utm_medium=badge&utm_campaign=badge-kdd" target="_blank" rel="noopener noreferrer"><picture><source media="(prefers-color-scheme: dark)" srcset="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1198446&theme=dark&t=1784571286941"><img alt="KDD - Govern AI agents with deterministic gates. No LLM judging. | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1198446&theme=light&t=1784571617560"></picture></a>

[English](#english) | [Español](#español) | [Português](#português)

<a id="english"></a>

## English

🌐 **[Landing page](https://mauricioperera.github.io/KDD/)** — a visual walkthrough of the methodology (EN/ES toggle).

This is a template repository for projects that implement the **Knowledge-Driven Development (KDD)** methodology, which unifies:
- **OKF (Open Knowledge Format):** A minimalist format for structuring knowledge, design, and architecture as markdown files with YAML frontmatter. The normative spec for OKF nodes lives in [`knowledge/OKF-SPEC.md`](knowledge/OKF-SPEC.md).
- **CCDD (Contract-Driven Development):** A methodology for governing development with ephemeral AI agents through strict contracts and deterministic thresholds (complexity, frozen tests).
- **Security (Capa 3):** Governs security findings with the same declarative rule engine as the other domains. Sealed `scan-manifest.json`/`findings.json`/`coverage.json` artifacts (schemas and sealer vendored from [openai/codex-security](https://github.com/openai/codex-security), Apache-2.0) are audited by [`examples/rules/security-findings.rules.json`](examples/rules/security-findings.rules.json); see [`knowledge/data_models/security_findings.md`](knowledge/data_models/security_findings.md) and the model-agnostic production skill at [`.agents/skills/kdd-security-scan/`](.agents/skills/kdd-security-scan/SKILL.md).
- **Compliance/licenses (Capa 3):** Governs dependency license-compatibility findings with the same rule engine, natively (no vendoring needed). Sealed `findings.json` artifacts are audited by [`examples/rules/compliance-findings.rules.json`](examples/rules/compliance-findings.rules.json); see [`knowledge/data_models/compliance_findings.md`](knowledge/data_models/compliance_findings.md) and the production skill at [`.agents/skills/kdd-compliance-scan/`](.agents/skills/kdd-compliance-scan/SKILL.md).
- **Privacy/PII (Capa 3):** Governs personal-data findings and their legal basis with the same rule engine, natively. Sealed `findings.json` artifacts are audited by [`examples/rules/privacy-findings.rules.json`](examples/rules/privacy-findings.rules.json); see [`knowledge/data_models/privacy_findings.md`](knowledge/data_models/privacy_findings.md) and the production skill at [`.agents/skills/kdd-privacy-scan/`](.agents/skills/kdd-privacy-scan/SKILL.md).
- **Accessibility (Capa 3):** Governs WCAG audit findings (axe-core/Lighthouse/pa11y/manual review) with the same rule engine, natively — distinct from the static `validate_ux_page.py` linter over the repo's own HTML pages. Sealed `findings.json` artifacts are audited by [`examples/rules/accessibility-findings.rules.json`](examples/rules/accessibility-findings.rules.json); see [`knowledge/data_models/accessibility_findings.md`](knowledge/data_models/accessibility_findings.md) and the production skill at [`.agents/skills/kdd-accessibility-scan/`](.agents/skills/kdd-accessibility-scan/SKILL.md).
- **Dependency EOL (Capa 3):** Governs dependency maintenance-health findings (outdated, unmaintained, past their publisher-declared end-of-life) with the same rule engine, natively — distinct from Compliance (license, not currency). Sealed `findings.json` artifacts are audited by [`examples/rules/dependency-eol-findings.rules.json`](examples/rules/dependency-eol-findings.rules.json); see [`knowledge/data_models/dependency_eol_findings.md`](knowledge/data_models/dependency_eol_findings.md) and the production skill at [`.agents/skills/kdd-dependency-eol-scan/`](.agents/skills/kdd-dependency-eol-scan/SKILL.md).
- **Observability (Capa 3):** Governs logging/alerting/tracing gap findings (silent failures, unlogged error paths, missing alerts on critical operations) with the same rule engine, natively. Sealed `findings.json` artifacts are audited by [`examples/rules/observability-findings.rules.json`](examples/rules/observability-findings.rules.json); see [`knowledge/data_models/observability_findings.md`](knowledge/data_models/observability_findings.md) and the production skill at [`.agents/skills/kdd-observability-scan/`](.agents/skills/kdd-observability-scan/SKILL.md).
- **Test coverage (Capa 3):** Governs test-coverage-gap findings (untested critical paths, uncovered error cases, missing regression tests) with the same rule engine, natively — distinct from CCDD's frozen-oracle discipline (per-contract test presence, already Level 1), which this domain complements rather than duplicates. Sealed `findings.json` artifacts are audited by [`examples/rules/test-coverage-findings.rules.json`](examples/rules/test-coverage-findings.rules.json); see [`knowledge/data_models/test_coverage_findings.md`](knowledge/data_models/test_coverage_findings.md) and the production skill at [`.agents/skills/kdd-test-coverage-scan/`](.agents/skills/kdd-test-coverage-scan/SKILL.md).

### Repository Structure

- `knowledge/`: Where your OKF knowledge base lives. Every file here is an indexable node.
- `knowledge/contracts/`: Where tasks for developers (human or AI) are defined using the hybrid OKF+CCDD format.
- `src/` and `tests/`: Implementation code and automated tests.
- `scripts/validate_contracts.py`: Deterministic contract validator (stdlib, no LLM, no network).
- `.agents/`: Local rules for AI agents that clone this repository.
- `specs/` and `docs/reports/`: Project-level **execution contracts** and their verified,
  in-repo reports (templates included). Task-level evidence stays local in `.agents/logs/`;
  see [`knowledge/metodologia-ejecucion.md`](knowledge/metodologia-ejecucion.md).
- `scripts/assemble_context.py` + `ccdd/context.json`: budgeted, deterministic context
  assembler over the OKF knowledge base (CCDD Level 2).
- `scripts/rule_engine.py` + `scripts/validate_rules.py`: the **rule-contract** layer —
  business rules validated as declarative data with a hash-sealed golden set (format:
  [`knowledge/rule-contract-spec.md`](knowledge/rule-contract-spec.md); examples under
  `examples/rules/`).

### How to use this template

1. Use this repository as a "Template" on GitHub or clone it locally.
2. Explore `knowledge/index.md` to see how concepts are structured.
3. When delegating work to an agent (e.g. an AI coding agent), the agent will read `.agents/AGENTS.md` and immediately understand that it must respect the CCDD contracts of this repository. Cursor, GitHub Copilot, Cline and Windsurf each have their own convention file (`.cursorrules`, `.github/copilot-instructions.md`, `.clinerules`, `.windsurfrules`) — all four are thin pointers to `.agents/AGENTS.md`, so any of those tools picks up the same rules automatically. For a human reviewing what an agent produced, see [`knowledge/supervision-humana.md`](knowledge/supervision-humana.md).
4. Drop the example artifacts and rewire `knowledge/index.md` with `python scripts/init_project.py --apply --name "<Your Project>"` (it removes every EXAMPLE artifact in the script's explicit `MANIFEST` — sample code and tests, the example OKF nodes, and every example domain (rule contracts, task contracts and their data-model nodes: payments, border control, workflows, routing, editorial, MCP registry, agent wiring); without `--apply` it only prints the plan).

#### Consuming the gates without a full clone (EN-only addition)

<!-- This subsection is the only EN-only addition for distributing the gates as reusable CI (ITEM4). -->

There are two complementary ways to run the KDD gates against your repo without copying the whole template:

- **Mode 1 — your repo is already a fork/clone of this template** (it has the vendored `scripts/` with the same structure). Call the reusable workflow directly:

  ```yaml
  jobs:
    kdd:
      uses: MauricioPerera/KDD/.github/workflows/validate.yml@main
      with:
        contracts_dir: knowledge/contracts   # override only the paths you moved
        specs_dir: specs
        okf_dir: knowledge
        # rules_dir, skills_dirs, ux_page_dir, diagrams_dir, src_dir_secrets
        # all have defaults matching the template; omit the ones you didn't move.
  ```

  Every input has a default equal to the template's hardcoded path, so a vanilla fork can call it with an empty `with:` block. (Note: these defaults apply only when called via `workflow_call`; the workflow's own native `push`/`pull_request` triggers fall back to the same literals embedded in the run expressions, so the KDD repo's own CI is unchanged.)

- **Mode 2 — your repo is NOT a fork of the template but has its own `knowledge/contracts/`** (no vendored `scripts/`). Use the composite action, which checks out this repo's tooling for you:

  ```yaml
  steps:
    - uses: actions/checkout@v4          # YOUR repo (the action assumes this is done first)
    - uses: MauricioPerera/KDD/.github/actions/validate-contracts@main
      with:
        kdd-ref: main                     # pin to a tag for reproducibility
        contracts-dir: knowledge/contracts
        okf-dir: knowledge
        # specs-dir is optional and auto-skipped if your repo has no specs/.
        # rules-dir / skills-dirs / ux-page-dir / diagrams-dir / src-dir
        # auto-skip (INFO, exit 0) when absent.
        # run-test-commands: 'true' also runs each contract's test_command.
  ```

  The action checks out `MauricioPerera/KDD` into `_kdd/` (not the root, so it does not overwrite your files) and runs the validators against your paths. `validate_contracts` and `validate_okf` are logically required (a missing dir is a real ERROR — it means there are no KDD contracts to validate); `validate_specs` is guarded so a repo without `specs/` stays green; the rest auto-skip. It deliberately does not run `lint_ascii`, the KDD unit-test suite, or `assemble_context` (those are specific to this repo's own tooling).

#### Instantiating for a non-Python project

This template's KDD tooling is Python and stays Python even if your project is not — these are two separate planes (template tooling vs. your project's code).

- **Kept unchanged:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/validate_skills.py`, `scripts/validate_changelog.py`, `scripts/validate_perimeter.py`, `scripts/benchmark_gates.py`, `scripts/validate_ux_page.py`, `scripts/validate_diagrams.py`, `scripts/validate_commit_message.py`, `scripts/rule_hints.py`, `scripts/export_gate_contract.py`, and `scripts/init_project.py` remain Python; they validate contracts and produce the gate export regardless of your project's language.
- **Adapted:** each contract's `test_command` must use your language's runner (`node --test ...`, `cargo test ...`, etc. — see the multi-language gate in [`knowledge/validacion.md`](knowledge/validacion.md)). The CI workflow `.github/workflows/validate.yml` runs on an OS matrix (`ubuntu-latest` + `windows-latest`), installs Python and runs the template's validators, the ASCII lint and the Python suite twice (`python -m unittest discover -s tests`, anti-flaky); a separate **"Run project test suite"** step is a placeholder for your own project's tests — swap its command for your language's runner (`npm test`, `cargo test`, `go test ./...`, ...) and add the matching `actions/setup-*` step above it if your runtime needs setup. The two Python steps before it are still required as-is: they validate the KDD tooling itself, not your project.
- **Example artifacts:** `scripts/init_project.py --apply` removes Python-written EXAMPLE artifacts (`src/hello.py`, `src/users.py`, the sample tests, the example OKF nodes) — they are only illustrative examples of the contract pattern, not a language dependency: they are removed the same way regardless of your project's language, and afterwards you add your own contracts/tests in your language.
- **Where YOUR project's tests go (`tests/` belongs to the tooling):** the inherited Python suite lives in `tests/` and is **not practically relocatable** — its ~37 files resolve `scripts/` assuming they sit exactly one level below the repo root, so moving them means editing and re-sealing every frozen oracle. If your language also uses `tests/` by convention (Rust is the clear case: cargo auto-discovers `tests/*.rs`), both planes end up in one directory. Nothing breaks — `unittest` discovers `test_*.py` and cargo only looks at `.rs` — but it becomes unreadable. **Recommendation: move your project's tests, not the tooling's**, using your language's own mechanism. In Rust it's three lines in `Cargo.toml` and the target name is unchanged, so the contract's `test_command` stays the same:
  ```toml
  [[test]]
  name = "my_test"
  path = "tests_rs/my_test.rs"
  ```
  Then update the contract's `tests:` key to the new path (the gate requires it: `FM_PATH_tests`). The `tests_sha256` does **not** change — it seals the oracle's content, not its location.

### Contract Validation, Budget Precedence, and Lifecycle

The full normative reference — validation levels 1 and 2, the multi-language gate, the gate export, budget precedence, and the `draft → verified` lifecycle — lives in the canonical OKF node [`knowledge/validacion.md`](knowledge/validacion.md). This README does not duplicate it (OKF §4). Summary:

- **Level 1 (included, mandatory):** `python scripts/validate_contracts.py knowledge/contracts` (includes the mandatory `tests_sha256` frozen-oracle seal and the mandatory `touch_only` perimeter key — see [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/validate_okf.py knowledge` (OKF node structure/frontmatter) + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — business rules as data, optional layer) + `python scripts/validate_skills.py skills .agents/skills` (agent-skill assets: structure, frontmatter, links, name uniqueness) + `python scripts/validate_changelog.py` (CHANGELOG↔reports coherence) + `python scripts/validate_ux_page.py examples/ux-page` (mechanical UX/accessibility on self-contained HTML pages, optional layer) + `python scripts/validate_diagrams.py examples/diagrams` (Mermaid diagram structure — flowchart/gantt/pie/journey, pure-Python parsers, optional layer; the sibling project [mermaid-gate](https://github.com/MauricioPerera/mermaid-gate) covers the other 16 diagram types with the real mermaid parser as an external tool, see `knowledge/diagram-contract-spec.md`) + the contract's `test_command`, all green locally and in CI (`.github/workflows/validate.yml`, dual-OS matrix). No contract is considered done until level 1 passes.
- **Level 2 (optional):** the real CCDD gate via the `ccdd-complexity` MCP server (`lint_task_contract`, `run_integration_gate`) over the export produced by `scripts/export_gate_contract.py`. With the gate present, its signed config takes precedence over the frontmatter `budget`.

### Versioning

The template uses **semantic versioning** starting from `v1.0.0`. See [`CHANGELOG.md`](CHANGELOG.md) for the release history. When you instantiate this template with `init_project`, you inherit a versioned base that you can upgrade: the [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) node documents which artifacts are template infrastructure (updatable from upstream) and which belong to your project (yours to keep or modify as you see fit).

<a id="español"></a>

## Español

🌐 **[Landing page](https://mauricioperera.github.io/KDD/)** — un recorrido visual de la metodología (toggle EN/ES).

Este repositorio plantilla es para proyectos que implementan la metodología **Knowledge-Driven Development (KDD)**, la cual unifica:
- **OKF (Open Knowledge Format):** Un formato minimalista para estructurar el conocimiento, diseño y arquitectura como archivos markdown con frontmatter YAML. La spec normativa de los nodos OKF está en [`knowledge/OKF-SPEC.md`](knowledge/OKF-SPEC.md).
- **CCDD (Contract-Driven Development):** Una metodología para gobernar el desarrollo con agentes de IA efímeros mediante contratos estrictos y umbrales deterministas (complejidad, tests congelados).
- **Seguridad (Capa 3):** Gobierna hallazgos de seguridad con el mismo motor de reglas declarativo que los demás dominios. Los artefactos sellados `scan-manifest.json`/`findings.json`/`coverage.json` (schemas y sellador vendorizados de [openai/codex-security](https://github.com/openai/codex-security), Apache-2.0) se auditan con [`examples/rules/security-findings.rules.json`](examples/rules/security-findings.rules.json); ver [`knowledge/data_models/security_findings.md`](knowledge/data_models/security_findings.md) y la skill de producción agnóstica de modelo en [`.agents/skills/kdd-security-scan/`](.agents/skills/kdd-security-scan/SKILL.md).
- **Compliance/licencias (Capa 3):** Gobierna hallazgos de compatibilidad de licencias de dependencias con el mismo motor de reglas, de forma nativa (sin vendoring). Los artefactos sellados `findings.json` se auditan con [`examples/rules/compliance-findings.rules.json`](examples/rules/compliance-findings.rules.json); ver [`knowledge/data_models/compliance_findings.md`](knowledge/data_models/compliance_findings.md) y la skill de producción en [`.agents/skills/kdd-compliance-scan/`](.agents/skills/kdd-compliance-scan/SKILL.md).
- **Privacidad/PII (Capa 3):** Gobierna hallazgos de datos personales y su base legal con el mismo motor de reglas, de forma nativa. Los artefactos sellados `findings.json` se auditan con [`examples/rules/privacy-findings.rules.json`](examples/rules/privacy-findings.rules.json); ver [`knowledge/data_models/privacy_findings.md`](knowledge/data_models/privacy_findings.md) y la skill de producción en [`.agents/skills/kdd-privacy-scan/`](.agents/skills/kdd-privacy-scan/SKILL.md).
- **Accesibilidad (Capa 3):** Gobierna hallazgos de auditoría WCAG (axe-core/Lighthouse/pa11y/revisión manual) con el mismo motor de reglas, de forma nativa — distinto del linter estático `validate_ux_page.py` sobre las páginas HTML propias del repo. Los artefactos sellados `findings.json` se auditan con [`examples/rules/accessibility-findings.rules.json`](examples/rules/accessibility-findings.rules.json); ver [`knowledge/data_models/accessibility_findings.md`](knowledge/data_models/accessibility_findings.md) y la skill de producción en [`.agents/skills/kdd-accessibility-scan/`](.agents/skills/kdd-accessibility-scan/SKILL.md).
- **Vigencia de dependencias / EOL (Capa 3):** Gobierna hallazgos de salud de mantenimiento de dependencias (desactualizadas, sin mantenimiento, fuera de la fecha de fin de vida declarada por su publisher) con el mismo motor de reglas, de forma nativa — distinto de Compliance (licencia, no vigencia). Los artefactos sellados `findings.json` se auditan con [`examples/rules/dependency-eol-findings.rules.json`](examples/rules/dependency-eol-findings.rules.json); ver [`knowledge/data_models/dependency_eol_findings.md`](knowledge/data_models/dependency_eol_findings.md) y la skill de producción en [`.agents/skills/kdd-dependency-eol-scan/`](.agents/skills/kdd-dependency-eol-scan/SKILL.md).
- **Observabilidad (Capa 3):** Gobierna hallazgos de gaps de logging/alertas/tracing (fallos silenciosos, rutas de error sin loguear, operaciones críticas sin alertas) con el mismo motor de reglas, de forma nativa. Los artefactos sellados `findings.json` se auditan con [`examples/rules/observability-findings.rules.json`](examples/rules/observability-findings.rules.json); ver [`knowledge/data_models/observability_findings.md`](knowledge/data_models/observability_findings.md) y la skill de producción en [`.agents/skills/kdd-observability-scan/`](.agents/skills/kdd-observability-scan/SKILL.md).
- **Cobertura de tests (Capa 3):** Gobierna hallazgos de gaps de cobertura (rutas críticas sin test, casos de error sin cubrir, regresiones sin atrapar) con el mismo motor de reglas, de forma nativa — distinto de la disciplina de oráculo congelado de CCDD (presencia de tests por contrato, ya Nivel 1), que este dominio complementa en vez de duplicar. Los artefactos sellados `findings.json` se auditan con [`examples/rules/test-coverage-findings.rules.json`](examples/rules/test-coverage-findings.rules.json); ver [`knowledge/data_models/test_coverage_findings.md`](knowledge/data_models/test_coverage_findings.md) y la skill de producción en [`.agents/skills/kdd-test-coverage-scan/`](.agents/skills/kdd-test-coverage-scan/SKILL.md).

### Estructura del Repositorio

- `knowledge/`: Aquí vive tu base de conocimiento OKF. Todo archivo aquí es un nodo indexable.
- `knowledge/contracts/`: Donde se definen las tareas para los desarrolladores (humanos o IA) usando el formato híbrido OKF+CCDD.
- `src/` y `tests/`: Código de implementación y pruebas automatizadas.
- `scripts/validate_contracts.py`: Validador determinista de contratos (stdlib, sin LLM, sin red).
- `.agents/`: Reglas locales para agentes de IA que clonen este repositorio.
- `specs/` y `docs/reports/`: **contratos de ejecución** de nivel proyecto y sus reportes
  verificados en-repo (plantillas incluidas). La evidencia de tarea sigue siendo local en
  `.agents/logs/`; ver [`knowledge/metodologia-ejecucion.md`](knowledge/metodologia-ejecucion.md).
- `scripts/assemble_context.py` + `ccdd/context.json`: ensamblador de contexto presupuestado
  y determinista sobre la KB OKF (CCDD Nivel 2).
- `scripts/rule_engine.py` + `scripts/validate_rules.py`: la capa de **rule contracts** —
  reglas de negocio validadas como datos declarativos con golden set sellado por hash
  (formato: [`knowledge/rule-contract-spec.md`](knowledge/rule-contract-spec.md); ejemplos
  en `examples/rules/`).

### Cómo usar esta plantilla

1. Usa este repositorio como "Template" en GitHub o clónalo localmente.
2. Explora `knowledge/index.md` para ver cómo se estructuran los conceptos.
3. Al delegar trabajo a un agente (ej. un agente de IA), el agente leerá `.agents/AGENTS.md` y entenderá inmediatamente que debe respetar los contratos CCDD de este repositorio. Cursor, GitHub Copilot, Cline y Windsurf tienen cada uno su propio archivo de convención (`.cursorrules`, `.github/copilot-instructions.md`, `.clinerules`, `.windsurfrules`) — los cuatro son punteros delgados a `.agents/AGENTS.md`, así que cualquiera de esas herramientas recibe las mismas reglas automáticamente. Para un humano que revisa lo que produjo un agente, ver [`knowledge/supervision-humana.md`](knowledge/supervision-humana.md).
4. Quita los artefactos de ejemplo y reescribe `knowledge/index.md` con `python scripts/init_project.py --apply --name "<Tu Proyecto>"` (elimina todos los artefactos de EJEMPLO del `MANIFEST` explícito del script — código y tests de muestra, los nodos OKF de ejemplo y todos los dominios de ejemplo (rule contracts, contratos de tarea y sus nodos: pagos, fronteras, workflows, ruteo, editorial, registro MCP, cableado de agentes); sin `--apply` solo imprime el plan).

#### Instanciar para un proyecto no-Python

El tooling KDD de esta plantilla es Python y sigue siéndolo aunque tu proyecto no lo sea — son dos planos distintos (tooling de la plantilla vs. código de tu proyecto).

- **Se conserva sin cambios:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/validate_skills.py`, `scripts/validate_changelog.py`, `scripts/validate_perimeter.py`, `scripts/benchmark_gates.py`, `scripts/validate_ux_page.py`, `scripts/validate_diagrams.py`, `scripts/rule_hints.py`, `scripts/export_gate_contract.py` y `scripts/init_project.py` siguen siendo Python; validan contratos y generan el export del gate sin importar el lenguaje de tu proyecto.
- **Se adapta:** el `test_command` de cada contrato debe usar el runner de tu lenguaje (`node --test ...`, `cargo test ...`, etc. — ver el gate multi-lenguaje en [`knowledge/validacion.md`](knowledge/validacion.md)). El workflow de CI `.github/workflows/validate.yml` corre en una matriz de OS (`ubuntu-latest` + `windows-latest`), instala Python y corre los validadores de la plantilla, el lint ASCII y la suite Python dos veces (`python -m unittest discover -s tests`, anti-flaky); un paso separado **"Run project test suite"** es un placeholder para los tests de tu propio proyecto — reemplaza su comando por el runner de tu lenguaje (`npm test`, `cargo test`, `go test ./...`, ...) y agrega el paso `actions/setup-*` correspondiente arriba si tu runtime necesita instalación. Los dos pasos Python anteriores siguen siendo necesarios tal cual: validan el tooling KDD mismo, no tu proyecto.
- **Artefactos de ejemplo:** `scripts/init_project.py --apply` borra artefactos de EJEMPLO escritos en Python (`src/hello.py`, `src/users.py`, los tests de ejemplo, los nodos OKF de ejemplo) — son solo ejemplos ilustrativos del patrón de contratos, no una dependencia de lenguaje: se borran igual sin importar el lenguaje de tu proyecto, y después agregas tus propios contratos/tests en tu lenguaje.
- **Dónde poner los tests de TU proyecto (`tests/` es del tooling):** la suite Python heredada vive en `tests/` y **no es reubicable en la práctica** — sus ~37 archivos resuelven `scripts/` asumiendo estar exactamente un nivel debajo de la raíz, así que moverlos obliga a editar y re-sellar cada oráculo congelado. Si tu lenguaje también usa `tests/` por convención (Rust es el caso claro: cargo autodescubre `tests/*.rs`), los dos planos terminan mezclados en un mismo directorio. No se rompe nada — `unittest` descubre `test_*.py` y cargo solo mira `.rs` — pero se vuelve ilegible. **Recomendación: mové los tests de tu proyecto, no los del tooling**, usando el mecanismo de tu lenguaje. En Rust son tres líneas en `Cargo.toml` y el nombre del target no cambia, así que el `test_command` del contrato queda igual:
  ```toml
  [[test]]
  name = "mi_test"
  path = "tests_rs/mi_test.rs"
  ```
  Después actualizá la clave `tests:` del contrato a la ruta nueva (el gate lo exige: `FM_PATH_tests`). El `tests_sha256` **no** cambia — sella el contenido del oráculo, no su ubicación.

### Validación de Contratos, Precedencia del Budget y Ciclo de Vida

La referencia normativa completa — niveles 1 y 2 de validación, el gate multi-lenguaje, el export para el gate, la precedencia del budget y el ciclo de vida `draft → verified` — vive en el nodo OKF canónico [`knowledge/validacion.md`](knowledge/validacion.md). Este README no la duplica (OKF §4). Resumen:

- **Nivel 1 (incluido, obligatorio):** `python scripts/validate_contracts.py knowledge/contracts` (incluye el sello obligatorio `tests_sha256` del oráculo congelado y la clave obligatoria de perímetro `touch_only` — ver [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/validate_okf.py knowledge` (estructura/frontmatter de nodos OKF) + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — reglas de negocio como datos, capa opcional) + `python scripts/validate_skills.py skills .agents/skills` (activos de skills de agente: estructura, frontmatter, enlaces, unicidad de nombres) + `python scripts/validate_changelog.py` (coherencia CHANGELOG↔reportes) + `python scripts/validate_ux_page.py examples/ux-page` (UX/accesibilidad mecánica sobre páginas HTML autocontenidas, capa opcional) + `python scripts/validate_diagrams.py examples/diagrams` (estructura de diagramas Mermaid — flowchart/gantt/pie/journey, parsers propios en Python puro, capa opcional; el proyecto hermano [mermaid-gate](https://github.com/MauricioPerera/mermaid-gate) cubre los otros 16 tipos de diagrama con el parser real de mermaid como herramienta externa, ver `knowledge/diagram-contract-spec.md`) + el `test_command` del contrato, todo en verde local y en CI (`.github/workflows/validate.yml`, matriz dual-OS). Ningún contrato se considera terminado hasta pasar el nivel 1.
- **Nivel 2 (opcional):** el gate CCDD real vía el servidor MCP `ccdd-complexity` (`lint_task_contract`, `run_integration_gate`) sobre el export de `scripts/export_gate_contract.py`. Con gate presente, su config firmada tiene precedencia sobre el `budget` del frontmatter.
- **Preflight (diagnóstico opt-in, no es un gate):** antes de delegar trabajo a un agente, corre `python scripts/preflight.py` para ver en una pasada local cuáles de los 19 gates (los 18 de Nivel 1 + `validate_attestation`, local-only) fallarían sobre el repo actual; modo `--contract <nombre>` acota a 3 chequeos de un task contract (ver [`knowledge/validacion.md`](knowledge/validacion.md)).
- **Auditor de seals débiles (advisory, no es un gate):** `python scripts/audit_seals.py [--strict]` detecta oráculos sellados que no pueden fallar (sin asserts reales, sin tests, sin referenciar al target); advisory por default (exit 0), `--strict` opt-in (ver [`knowledge/validacion.md`](knowledge/validacion.md)).
- **Recetas de arreglo (diagnóstico opt-in, no es un gate):** los gates dicen *qué* falló, no *qué hacer*. `python scripts/rule_hints.py <RULE_ID>` da la receta de cualquiera de los 107 rule-ids que emiten los validadores, y `python scripts/preflight.py --agent` corre el preflight con la receta de cada gate en rojo ya adjunta (ver [`knowledge/validacion.md`](knowledge/validacion.md)).

### Versionado

La plantilla usa **versionado semántico** comenzando desde `v1.0.0`. Consulta [`CHANGELOG.md`](CHANGELOG.md) para el historial de releases. Cuando instancies esta plantilla con `init_project`, heredas una base versionada que puedes actualizar: el nodo [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) documenta cuál es infraestructura de la plantilla (actualizable desde upstream) y cuál pertenece a tu proyecto (tuyo para mantener o modificar).

<a id="português"></a>

## Português

🌐 **[Landing page](https://mauricioperera.github.io/KDD/)** — um passeio visual pela metodologia (alternância EN/ES/PT).

Este é um repositório-modelo para projetos que implementam a metodologia **Knowledge-Driven Development (KDD)**, que unifica:
- **OKF (Open Knowledge Format):** Um formato minimalista para estruturar conhecimento, design e arquitetura como arquivos markdown com frontmatter YAML. A especificação normativa dos nós OKF está em [`knowledge/OKF-SPEC.md`](knowledge/OKF-SPEC.md).
- **CCDD (Contract-Driven Development):** Uma metodologia para governar o desenvolvimento com agentes de IA efêmeros por meio de contratos estritos e limiares determinísticos (complexidade, testes congelados).
- **Segurança (Camada 3):** Governa achados de segurança com o mesmo motor de regras declarativo dos demais domínios. Os artefatos selados `scan-manifest.json`/`findings.json`/`coverage.json` (schemas e selador vendorizados de [openai/codex-security](https://github.com/openai/codex-security), Apache-2.0) são auditados por [`examples/rules/security-findings.rules.json`](examples/rules/security-findings.rules.json); veja [`knowledge/data_models/security_findings.md`](knowledge/data_models/security_findings.md) e a skill de produção agnóstica de modelo em [`.agents/skills/kdd-security-scan/`](.agents/skills/kdd-security-scan/SKILL.md).
- **Compliance/licenças (Camada 3):** Governa achados de compatibilidade de licenças de dependências com o mesmo motor de regras, de forma nativa (sem vendoring). Os artefatos selados `findings.json` são auditados por [`examples/rules/compliance-findings.rules.json`](examples/rules/compliance-findings.rules.json); veja [`knowledge/data_models/compliance_findings.md`](knowledge/data_models/compliance_findings.md) e a skill de produção em [`.agents/skills/kdd-compliance-scan/`](.agents/skills/kdd-compliance-scan/SKILL.md).
- **Privacidade/PII (Camada 3):** Governa achados de dados pessoais e sua base legal com o mesmo motor de regras, de forma nativa. Os artefatos selados `findings.json` são auditados por [`examples/rules/privacy-findings.rules.json`](examples/rules/privacy-findings.rules.json); veja [`knowledge/data_models/privacy_findings.md`](knowledge/data_models/privacy_findings.md) e a skill de produção em [`.agents/skills/kdd-privacy-scan/`](.agents/skills/kdd-privacy-scan/SKILL.md).
- **Acessibilidade (Camada 3):** Governa achados de auditoria WCAG (axe-core/Lighthouse/pa11y/revisão manual) com o mesmo motor de regras, de forma nativa — diferente do linter estático `validate_ux_page.py` sobre as páginas HTML próprias do repo. Os artefatos selados `findings.json` são auditados por [`examples/rules/accessibility-findings.rules.json`](examples/rules/accessibility-findings.rules.json); veja [`knowledge/data_models/accessibility_findings.md`](knowledge/data_models/accessibility_findings.md) e a skill de produção em [`.agents/skills/kdd-accessibility-scan/`](.agents/skills/kdd-accessibility-scan/SKILL.md).
- **Vigência de dependências / EOL (Camada 3):** Governa achados de saúde de manutenção de dependências (desatualizadas, sem manutenção, além da data de fim de vida declarada pelo publisher) com o mesmo motor de regras, de forma nativa — diferente de Compliance (licença, não vigência). Os artefatos selados `findings.json` são auditados por [`examples/rules/dependency-eol-findings.rules.json`](examples/rules/dependency-eol-findings.rules.json); veja [`knowledge/data_models/dependency_eol_findings.md`](knowledge/data_models/dependency_eol_findings.md) e a skill de produção em [`.agents/skills/kdd-dependency-eol-scan/`](.agents/skills/kdd-dependency-eol-scan/SKILL.md).
- **Observabilidade (Camada 3):** Governa achados de gaps de logging/alertas/tracing (falhas silenciosas, rotas de erro sem log, operações críticas sem alertas) com o mesmo motor de regras, de forma nativa. Os artefatos selados `findings.json` são auditados por [`examples/rules/observability-findings.rules.json`](examples/rules/observability-findings.rules.json); veja [`knowledge/data_models/observability_findings.md`](knowledge/data_models/observability_findings.md) e a skill de produção em [`.agents/skills/kdd-observability-scan/`](.agents/skills/kdd-observability-scan/SKILL.md).
- **Cobertura de testes (Camada 3):** Governa achados de gaps de cobertura (rotas críticas sem teste, casos de erro não cobertos, regressões não detectadas) com o mesmo motor de regras, de forma nativa — diferente da disciplina de oráculo congelado do CCDD (presença de testes por contrato, já Nível 1), que este domínio complementa em vez de duplicar. Os artefatos selados `findings.json` são auditados por [`examples/rules/test-coverage-findings.rules.json`](examples/rules/test-coverage-findings.rules.json); veja [`knowledge/data_models/test_coverage_findings.md`](knowledge/data_models/test_coverage_findings.md) e a skill de produção em [`.agents/skills/kdd-test-coverage-scan/`](.agents/skills/kdd-test-coverage-scan/SKILL.md).

### Estrutura do Repositório

- `knowledge/`: Onde vive sua base de conhecimento OKF. Todo arquivo aqui é um nó indexável.
- `knowledge/contracts/`: Onde as tarefas para desenvolvedores (humanos ou IA) são definidas usando o formato híbrido OKF+CCDD.
- `src/` e `tests/`: Código de implementação e testes automatizados.
- `scripts/validate_contracts.py`: Validador determinístico de contratos (stdlib, sem LLM, sem rede).
- `.agents/`: Regras locais para agentes de IA que clonarem este repositório.
- `specs/` e `docs/reports/`: **contratos de execução** em nível de projeto e seus relatórios
  verificados no próprio repositório (templates incluídos). A evidência em nível de tarefa
  permanece local em `.agents/logs/`; veja
  [`knowledge/metodologia-ejecucion.md`](knowledge/metodologia-ejecucion.md).
- `scripts/assemble_context.py` + `ccdd/context.json`: montador de contexto orçado e
  determinístico sobre a base de conhecimento OKF (CCDD Nível 2).
- `scripts/rule_engine.py` + `scripts/validate_rules.py`: a camada de **rule contracts** —
  regras de negócio validadas como dados declarativos com um golden set selado por hash
  (formato: [`knowledge/rule-contract-spec.md`](knowledge/rule-contract-spec.md); exemplos
  em `examples/rules/`).

### Como usar este modelo

1. Use este repositório como "Template" no GitHub ou clone-o localmente.
2. Explore `knowledge/index.md` para ver como os conceitos são estruturados.
3. Ao delegar trabalho a um agente (ex.: um agente de codificação de IA), o agente lerá `.agents/AGENTS.md` e entenderá imediatamente que deve respeitar os contratos CCDD deste repositório.
4. Remova os artefatos de exemplo e reescreva `knowledge/index.md` com `python scripts/init_project.py --apply --name "<Seu Projeto>"` (remove todo artefato de EXEMPLO no `MANIFEST` explícito do script — código e testes de amostra, os nós OKF de exemplo e todos os domínios de exemplo (rule contracts, contratos de tarefa e seus nós de modelo de dados: pagamentos, controle de fronteira, workflows, roteamento, editorial, registro MCP, cabeamento de agentes); sem `--apply` ele apenas imprime o plano).

#### Instanciando para um projeto não-Python

O tooling KDD deste modelo é Python e continua sendo Python mesmo que seu projeto não seja — são dois planos separados (tooling do modelo vs. código do seu projeto).

- **Mantido sem alterações:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/validate_skills.py`, `scripts/validate_changelog.py`, `scripts/validate_perimeter.py`, `scripts/benchmark_gates.py`, `scripts/validate_ux_page.py`, `scripts/validate_diagrams.py`, `scripts/validate_commit_message.py`, `scripts/rule_hints.py`, `scripts/export_gate_contract.py` e `scripts/init_project.py` continuam sendo Python; eles validam contratos e produzem o export do gate independentemente do idioma do seu projeto.
- **Adaptado:** o `test_command` de cada contrato deve usar o executor do seu idioma (`node --test ...`, `cargo test ...`, etc. — veja o gate multilíngue em [`knowledge/validacion.md`](knowledge/validacion.md)). O workflow de CI `.github/workflows/validate.yml` roda em uma matriz de SO (`ubuntu-latest` + `windows-latest`), instala Python e executa os validadores do modelo, o lint ASCII e a suíte Python duas vezes (`python -m unittest discover -s tests`, anti-flaky); um passo separado **"Run project test suite"** é um placeholder para os testes do seu próprio projeto — troque o comando pelo executor do seu idioma (`npm test`, `cargo test`, `go test ./...`, ...) e adicione o passo `actions/setup-*` correspondente acima se seu runtime precisar de configuração. Os dois passos Python anteriores continuam sendo necessários como estão: eles validam o próprio tooling KDD, não o seu projeto.
- **Artefatos de exemplo:** `scripts/init_project.py --apply` remove artefatos de EXEMPLO escritos em Python (`src/hello.py`, `src/users.py`, os testes de amostra, os nós OKF de exemplo) — são apenas exemplos ilustrativos do padrão de contrato, não uma dependência de linguagem: são removidos da mesma forma independentemente do idioma do seu projeto, e depois você adiciona seus próprios contratos/testes no seu idioma.

### Validação de Contratos, Precedência de Budget e Ciclo de Vida

A referência normativa completa — níveis de validação 1 e 2, o gate multilíngue, o export do gate, a precedência de budget e o ciclo de vida `draft → verified` — vive no nó OKF canônico [`knowledge/validacion.md`](knowledge/validacion.md). Este README não a duplica (OKF §4). Resumo:

- **Nível 1 (incluído, obrigatório):** `python scripts/validate_contracts.py knowledge/contracts` (inclui o selo obrigatório `tests_sha256` do oráculo congelado e a chave obrigatória de perímetro `touch_only` — veja [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/validate_okf.py knowledge` (estrutura/frontmatter dos nós OKF) + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — regras de negócio como dados, camada opcional) + `python scripts/validate_skills.py skills .agents/skills` (ativos de skills de agente: estrutura, frontmatter, links, unicidade de nomes) + `python scripts/validate_changelog.py` (coerência CHANGELOG↔relatórios) + `python scripts/validate_ux_page.py examples/ux-page` (UX/acessibilidade mecânica sobre páginas HTML autocontidas, camada opcional) + `python scripts/validate_diagrams.py examples/diagrams` (estrutura de diagramas Mermaid — flowchart/gantt/pie/journey, parsers próprios em Python puro, camada opcional; o projeto irmão [mermaid-gate](https://github.com/MauricioPerera/mermaid-gate) cobre os outros 16 tipos de diagrama com o parser real do mermaid como ferramenta externa, veja `knowledge/diagram-contract-spec.md`) + o `test_command` do contrato, tudo verde localmente e no CI (`.github/workflows/validate.yml`, matriz dual-SO). Nenhum contrato é considerado concluído até passar o nível 1.
- **Nível 2 (opcional):** o gate CCDD real via o servidor MCP `ccdd-complexity` (`lint_task_contract`, `run_integration_gate`) sobre o export de `scripts/export_gate_contract.py`. Com o gate presente, sua config assinada tem precedência sobre o `budget` do frontmatter.

### Versionamento

O modelo usa **versionamento semântico** começando em `v1.0.0`. Veja [`CHANGELOG.md`](CHANGELOG.md) para o histórico de releases. Quando você instanciar este modelo com `init_project`, você herda uma base versionada que pode atualizar: o nó [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) documenta o que é infraestrutura do modelo (atualizável a partir do upstream) e o que pertence ao seu projeto (seu, para manter ou modificar como preferir).