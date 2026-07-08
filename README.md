# KDD Template (Knowledge-Driven Development)

[English](#english) | [Español](#español)

<a id="english"></a>

## English

This is a template repository for projects that implement the **Knowledge-Driven Development (KDD)** methodology, which unifies:
- **OKF (Open Knowledge Format):** A minimalist format for structuring knowledge, design, and architecture as markdown files with YAML frontmatter. The normative spec for OKF nodes lives in [`knowledge/OKF-SPEC.md`](knowledge/OKF-SPEC.md).
- **CCDD (Contract-Driven Development):** A methodology for governing development with ephemeral AI agents through strict contracts and deterministic thresholds (complexity, frozen tests).

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
3. When delegating work to an agent (e.g. an AI coding agent), the agent will read `.agents/AGENTS.md` and immediately understand that it must respect the CCDD contracts of this repository.
4. Drop the example artifacts and rewire `knowledge/index.md` with `python scripts/init_project.py --apply --name "<Your Project>"` (it removes every EXAMPLE artifact in the script's explicit `MANIFEST` — sample code and tests, the example OKF nodes, and the payment/border-control rule-contract examples; without `--apply` it only prints the plan).

#### Instantiating for a non-Python project

This template's KDD tooling is Python and stays Python even if your project is not — these are two separate planes (template tooling vs. your project's code).

- **Kept unchanged:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/export_gate_contract.py`, and `scripts/init_project.py` remain Python; they validate contracts and produce the gate export regardless of your project's language.
- **Adapted:** each contract's `test_command` must use your language's runner (`node --test ...`, `cargo test ...`, etc. — see the multi-language gate in [`knowledge/validacion.md`](knowledge/validacion.md)). The CI workflow `.github/workflows/validate.yml` runs on an OS matrix (`ubuntu-latest` + `windows-latest`), installs Python and runs the template's validators, the ASCII lint and the Python suite twice (`python -m unittest discover -s tests`, anti-flaky); if your project adds code/tests in another language, you add an extra CI step (e.g. `actions/setup-node` + `npm test`) so that suite also runs in CI. The existing Python step is still required because it validates the KDD tooling itself.
- **Example artifacts:** `scripts/init_project.py --apply` removes Python-written EXAMPLE artifacts (`src/hello.py`, `src/users.py`, the sample tests, the example OKF nodes) — they are only illustrative examples of the contract pattern, not a language dependency: they are removed the same way regardless of your project's language, and afterwards you add your own contracts/tests in your language.

### Contract Validation, Budget Precedence, and Lifecycle

The full normative reference — validation levels 1 and 2, the multi-language gate, the gate export, budget precedence, and the `draft → verified` lifecycle — lives in the canonical OKF node [`knowledge/validacion.md`](knowledge/validacion.md). This README does not duplicate it (OKF §4). Summary:

- **Level 1 (included, mandatory):** `python scripts/validate_contracts.py knowledge/contracts` (includes the mandatory `tests_sha256` frozen-oracle seal — see [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — business rules as data, optional layer) + the contract's `test_command`, all green locally and in CI (`.github/workflows/validate.yml`, dual-OS matrix). No contract is considered done until level 1 passes.
- **Level 2 (optional):** the real CCDD gate via the `ccdd-complexity` MCP server (`lint_task_contract`, `run_integration_gate`) over the export produced by `scripts/export_gate_contract.py`. With the gate present, its signed config takes precedence over the frontmatter `budget`.

### Versioning

The template uses **semantic versioning** starting from `v1.0.0`. See [`CHANGELOG.md`](CHANGELOG.md) for the release history. When you instantiate this template with `init_project`, you inherit a versioned base that you can upgrade: the [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) node documents which artifacts are template infrastructure (updatable from upstream) and which belong to your project (yours to keep or modify as you see fit).

<a id="español"></a>

## Español

Este repositorio plantilla es para proyectos que implementan la metodología **Knowledge-Driven Development (KDD)**, la cual unifica:
- **OKF (Open Knowledge Format):** Un formato minimalista para estructurar el conocimiento, diseño y arquitectura como archivos markdown con frontmatter YAML. La spec normativa de los nodos OKF está en [`knowledge/OKF-SPEC.md`](knowledge/OKF-SPEC.md).
- **CCDD (Contract-Driven Development):** Una metodología para gobernar el desarrollo con agentes de IA efímeros mediante contratos estrictos y umbrales deterministas (complejidad, tests congelados).

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
3. Al delegar trabajo a un agente (ej. un agente de IA), el agente leerá `.agents/AGENTS.md` y entenderá inmediatamente que debe respetar los contratos CCDD de este repositorio.
4. Quita los artefactos de ejemplo y reescribe `knowledge/index.md` con `python scripts/init_project.py --apply --name "<Tu Proyecto>"` (elimina todos los artefactos de EJEMPLO del `MANIFEST` explícito del script — código y tests de muestra, los nodos OKF de ejemplo y los rule contracts de ejemplo de pagos/fronteras; sin `--apply` solo imprime el plan).

#### Instanciar para un proyecto no-Python

El tooling KDD de esta plantilla es Python y sigue siéndolo aunque tu proyecto no lo sea — son dos planos distintos (tooling de la plantilla vs. código de tu proyecto).

- **Se conserva sin cambios:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/export_gate_contract.py` y `scripts/init_project.py` siguen siendo Python; validan contratos y generan el export del gate sin importar el lenguaje de tu proyecto.
- **Se adapta:** el `test_command` de cada contrato debe usar el runner de tu lenguaje (`node --test ...`, `cargo test ...`, etc. — ver el gate multi-lenguaje en [`knowledge/validacion.md`](knowledge/validacion.md)). El workflow de CI `.github/workflows/validate.yml` corre en una matriz de OS (`ubuntu-latest` + `windows-latest`), instala Python y corre los validadores de la plantilla, el lint ASCII y la suite Python dos veces (`python -m unittest discover -s tests`, anti-flaky); si tu proyecto agrega código/tests en otro lenguaje, agregas un paso de CI adicional (ej. `actions/setup-node` + `npm test`) para que esa suite también corra en CI. El paso Python existente sigue siendo necesario porque valida el tooling KDD mismo.
- **Artefactos de ejemplo:** `scripts/init_project.py --apply` borra artefactos de EJEMPLO escritos en Python (`src/hello.py`, `src/users.py`, los tests de ejemplo, los nodos OKF de ejemplo) — son solo ejemplos ilustrativos del patrón de contratos, no una dependencia de lenguaje: se borran igual sin importar el lenguaje de tu proyecto, y después agregas tus propios contratos/tests en tu lenguaje.

### Validación de Contratos, Precedencia del Budget y Ciclo de Vida

La referencia normativa completa — niveles 1 y 2 de validación, el gate multi-lenguaje, el export para el gate, la precedencia del budget y el ciclo de vida `draft → verified` — vive en el nodo OKF canónico [`knowledge/validacion.md`](knowledge/validacion.md). Este README no la duplica (OKF §4). Resumen:

- **Nivel 1 (incluido, obligatorio):** `python scripts/validate_contracts.py knowledge/contracts` (incluye el sello obligatorio `tests_sha256` del oráculo congelado — ver [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — reglas de negocio como datos, capa opcional) + el `test_command` del contrato, todo en verde local y en CI (`.github/workflows/validate.yml`, matriz dual-OS). Ningún contrato se considera terminado hasta pasar el nivel 1.
- **Nivel 2 (opcional):** el gate CCDD real vía el servidor MCP `ccdd-complexity` (`lint_task_contract`, `run_integration_gate`) sobre el export de `scripts/export_gate_contract.py`. Con gate presente, su config firmada tiene precedencia sobre el `budget` del frontmatter.

### Versionado

La plantilla usa **versionado semántico** comenzando desde `v1.0.0`. Consulta [`CHANGELOG.md`](CHANGELOG.md) para el historial de releases. Cuando instancies esta plantilla con `init_project`, heredas una base versionada que puedes actualizar: el nodo [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) documenta cuál es infraestructura de la plantilla (actualizable desde upstream) y cuál pertenece a tu proyecto (tuyo para mantener o modificar).