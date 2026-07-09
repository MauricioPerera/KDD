# KDD Template (Knowledge-Driven Development)

[English](#english) | [Español](#español) | [Português](#português)

<a id="english"></a>

## English

🌐 **[Landing page](https://mauricioperera.github.io/KDD/)** — a visual walkthrough of the methodology (EN/ES toggle).

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
4. Drop the example artifacts and rewire `knowledge/index.md` with `python scripts/init_project.py --apply --name "<Your Project>"` (it removes every EXAMPLE artifact in the script's explicit `MANIFEST` — sample code and tests, the example OKF nodes, and every example domain (rule contracts, task contracts and their data-model nodes: payments, border control, workflows, routing, editorial, MCP registry, agent wiring); without `--apply` it only prints the plan).

#### Instantiating for a non-Python project

This template's KDD tooling is Python and stays Python even if your project is not — these are two separate planes (template tooling vs. your project's code).

- **Kept unchanged:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/validate_skills.py`, `scripts/validate_changelog.py`, `scripts/validate_perimeter.py`, `scripts/benchmark_gates.py`, `scripts/validate_ux_page.py`, `scripts/validate_commit_message.py`, `scripts/export_gate_contract.py`, and `scripts/init_project.py` remain Python; they validate contracts and produce the gate export regardless of your project's language.
- **Adapted:** each contract's `test_command` must use your language's runner (`node --test ...`, `cargo test ...`, etc. — see the multi-language gate in [`knowledge/validacion.md`](knowledge/validacion.md)). The CI workflow `.github/workflows/validate.yml` runs on an OS matrix (`ubuntu-latest` + `windows-latest`), installs Python and runs the template's validators, the ASCII lint and the Python suite twice (`python -m unittest discover -s tests`, anti-flaky); a separate **"Run project test suite"** step is a placeholder for your own project's tests — swap its command for your language's runner (`npm test`, `cargo test`, `go test ./...`, ...) and add the matching `actions/setup-*` step above it if your runtime needs setup. The two Python steps before it are still required as-is: they validate the KDD tooling itself, not your project.
- **Example artifacts:** `scripts/init_project.py --apply` removes Python-written EXAMPLE artifacts (`src/hello.py`, `src/users.py`, the sample tests, the example OKF nodes) — they are only illustrative examples of the contract pattern, not a language dependency: they are removed the same way regardless of your project's language, and afterwards you add your own contracts/tests in your language.

### Contract Validation, Budget Precedence, and Lifecycle

The full normative reference — validation levels 1 and 2, the multi-language gate, the gate export, budget precedence, and the `draft → verified` lifecycle — lives in the canonical OKF node [`knowledge/validacion.md`](knowledge/validacion.md). This README does not duplicate it (OKF §4). Summary:

- **Level 1 (included, mandatory):** `python scripts/validate_contracts.py knowledge/contracts` (includes the mandatory `tests_sha256` frozen-oracle seal and the mandatory `touch_only` perimeter key — see [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/validate_okf.py knowledge` (OKF node structure/frontmatter) + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — business rules as data, optional layer) + `python scripts/validate_skills.py skills .agents/skills` (agent-skill assets: structure, frontmatter, links, name uniqueness) + `python scripts/validate_changelog.py` (CHANGELOG↔reports coherence) + `python scripts/validate_ux_page.py examples/ux-page` (mechanical UX/accessibility on self-contained HTML pages, optional layer) + the contract's `test_command`, all green locally and in CI (`.github/workflows/validate.yml`, dual-OS matrix). No contract is considered done until level 1 passes.
- **Level 2 (optional):** the real CCDD gate via the `ccdd-complexity` MCP server (`lint_task_contract`, `run_integration_gate`) over the export produced by `scripts/export_gate_contract.py`. With the gate present, its signed config takes precedence over the frontmatter `budget`.

### Versioning

The template uses **semantic versioning** starting from `v1.0.0`. See [`CHANGELOG.md`](CHANGELOG.md) for the release history. When you instantiate this template with `init_project`, you inherit a versioned base that you can upgrade: the [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) node documents which artifacts are template infrastructure (updatable from upstream) and which belong to your project (yours to keep or modify as you see fit).

<a id="español"></a>

## Español

🌐 **[Landing page](https://mauricioperera.github.io/KDD/)** — un recorrido visual de la metodología (toggle EN/ES).

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
4. Quita los artefactos de ejemplo y reescribe `knowledge/index.md` con `python scripts/init_project.py --apply --name "<Tu Proyecto>"` (elimina todos los artefactos de EJEMPLO del `MANIFEST` explícito del script — código y tests de muestra, los nodos OKF de ejemplo y todos los dominios de ejemplo (rule contracts, contratos de tarea y sus nodos: pagos, fronteras, workflows, ruteo, editorial, registro MCP, cableado de agentes); sin `--apply` solo imprime el plan).

#### Instanciar para un proyecto no-Python

El tooling KDD de esta plantilla es Python y sigue siéndolo aunque tu proyecto no lo sea — son dos planos distintos (tooling de la plantilla vs. código de tu proyecto).

- **Se conserva sin cambios:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/validate_skills.py`, `scripts/validate_changelog.py`, `scripts/validate_perimeter.py`, `scripts/benchmark_gates.py`, `scripts/validate_ux_page.py`, `scripts/export_gate_contract.py` y `scripts/init_project.py` siguen siendo Python; validan contratos y generan el export del gate sin importar el lenguaje de tu proyecto.
- **Se adapta:** el `test_command` de cada contrato debe usar el runner de tu lenguaje (`node --test ...`, `cargo test ...`, etc. — ver el gate multi-lenguaje en [`knowledge/validacion.md`](knowledge/validacion.md)). El workflow de CI `.github/workflows/validate.yml` corre en una matriz de OS (`ubuntu-latest` + `windows-latest`), instala Python y corre los validadores de la plantilla, el lint ASCII y la suite Python dos veces (`python -m unittest discover -s tests`, anti-flaky); un paso separado **"Run project test suite"** es un placeholder para los tests de tu propio proyecto — reemplazá su comando por el runner de tu lenguaje (`npm test`, `cargo test`, `go test ./...`, ...) y agregá el paso `actions/setup-*` correspondiente arriba si tu runtime necesita instalación. Los dos pasos Python anteriores siguen siendo necesarios tal cual: validan el tooling KDD mismo, no tu proyecto.
- **Artefactos de ejemplo:** `scripts/init_project.py --apply` borra artefactos de EJEMPLO escritos en Python (`src/hello.py`, `src/users.py`, los tests de ejemplo, los nodos OKF de ejemplo) — son solo ejemplos ilustrativos del patrón de contratos, no una dependencia de lenguaje: se borran igual sin importar el lenguaje de tu proyecto, y después agregas tus propios contratos/tests en tu lenguaje.

### Validación de Contratos, Precedencia del Budget y Ciclo de Vida

La referencia normativa completa — niveles 1 y 2 de validación, el gate multi-lenguaje, el export para el gate, la precedencia del budget y el ciclo de vida `draft → verified` — vive en el nodo OKF canónico [`knowledge/validacion.md`](knowledge/validacion.md). Este README no la duplica (OKF §4). Resumen:

- **Nivel 1 (incluido, obligatorio):** `python scripts/validate_contracts.py knowledge/contracts` (incluye el sello obligatorio `tests_sha256` del oráculo congelado y la clave obligatoria de perímetro `touch_only` — ver [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/validate_okf.py knowledge` (estructura/frontmatter de nodos OKF) + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — reglas de negocio como datos, capa opcional) + `python scripts/validate_skills.py skills .agents/skills` (activos de skills de agente: estructura, frontmatter, enlaces, unicidad de nombres) + `python scripts/validate_changelog.py` (coherencia CHANGELOG↔reportes) + `python scripts/validate_ux_page.py examples/ux-page` (UX/accesibilidad mecánica sobre páginas HTML autocontenidas, capa opcional) + el `test_command` del contrato, todo en verde local y en CI (`.github/workflows/validate.yml`, matriz dual-OS). Ningún contrato se considera terminado hasta pasar el nivel 1.
- **Nivel 2 (opcional):** el gate CCDD real vía el servidor MCP `ccdd-complexity` (`lint_task_contract`, `run_integration_gate`) sobre el export de `scripts/export_gate_contract.py`. Con gate presente, su config firmada tiene precedencia sobre el `budget` del frontmatter.

### Versionado

La plantilla usa **versionado semántico** comenzando desde `v1.0.0`. Consulta [`CHANGELOG.md`](CHANGELOG.md) para el historial de releases. Cuando instancies esta plantilla con `init_project`, heredas una base versionada que puedes actualizar: el nodo [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) documenta cuál es infraestructura de la plantilla (actualizable desde upstream) y cuál pertenece a tu proyecto (tuyo para mantener o modificar).

<a id="português"></a>

## Português

🌐 **[Landing page](https://mauricioperera.github.io/KDD/)** — um passeio visual pela metodologia (alternância EN/ES/PT).

Este é um repositório-modelo para projetos que implementam a metodologia **Knowledge-Driven Development (KDD)**, que unifica:
- **OKF (Open Knowledge Format):** Um formato minimalista para estruturar conhecimento, design e arquitetura como arquivos markdown com frontmatter YAML. A especificação normativa dos nós OKF está em [`knowledge/OKF-SPEC.md`](knowledge/OKF-SPEC.md).
- **CCDD (Contract-Driven Development):** Uma metodologia para governar o desenvolvimento com agentes de IA efêmeros por meio de contratos estritos e limiares determinísticos (complexidade, testes congelados).

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

- **Mantido sem alterações:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/lint_ascii.py`, `scripts/rule_engine.py`, `scripts/validate_rules.py`, `scripts/validate_skills.py`, `scripts/validate_changelog.py`, `scripts/validate_perimeter.py`, `scripts/benchmark_gates.py`, `scripts/validate_ux_page.py`, `scripts/validate_commit_message.py`, `scripts/export_gate_contract.py` e `scripts/init_project.py` continuam sendo Python; eles validam contratos e produzem o export do gate independentemente do idioma do seu projeto.
- **Adaptado:** o `test_command` de cada contrato deve usar o executor do seu idioma (`node --test ...`, `cargo test ...`, etc. — veja o gate multilíngue em [`knowledge/validacion.md`](knowledge/validacion.md)). O workflow de CI `.github/workflows/validate.yml` roda em uma matriz de SO (`ubuntu-latest` + `windows-latest`), instala Python e executa os validadores do modelo, o lint ASCII e a suíte Python duas vezes (`python -m unittest discover -s tests`, anti-flaky); um passo separado **"Run project test suite"** é um placeholder para os testes do seu próprio projeto — troque o comando pelo executor do seu idioma (`npm test`, `cargo test`, `go test ./...`, ...) e adicione o passo `actions/setup-*` correspondente acima se seu runtime precisar de configuração. Os dois passos Python anteriores continuam sendo necessários como estão: eles validam o próprio tooling KDD, não o seu projeto.
- **Artefatos de exemplo:** `scripts/init_project.py --apply` remove artefatos de EXEMPLO escritos em Python (`src/hello.py`, `src/users.py`, os testes de amostra, os nós OKF de exemplo) — são apenas exemplos ilustrativos do padrão de contrato, não uma dependência de linguagem: são removidos da mesma forma independentemente do idioma do seu projeto, e depois você adiciona seus próprios contratos/testes no seu idioma.

### Validação de Contratos, Precedência de Budget e Ciclo de Vida

A referência normativa completa — níveis de validação 1 e 2, o gate multilíngue, o export do gate, a precedência de budget e o ciclo de vida `draft → verified` — vive no nó OKF canônico [`knowledge/validacion.md`](knowledge/validacion.md). Este README não a duplica (OKF §4). Resumo:

- **Nível 1 (incluído, obrigatório):** `python scripts/validate_contracts.py knowledge/contracts` (inclui o selo obrigatório `tests_sha256` do oráculo congelado e a chave obrigatória de perímetro `touch_only` — veja [`knowledge/validacion.md`](knowledge/validacion.md)) + `python scripts/validate_specs.py specs` + `python scripts/validate_okf.py knowledge` (estrutura/frontmatter dos nós OKF) + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py examples/rules` (rule contracts — regras de negócio como dados, camada opcional) + `python scripts/validate_skills.py skills .agents/skills` (ativos de skills de agente: estrutura, frontmatter, links, unicidade de nomes) + `python scripts/validate_changelog.py` (coerência CHANGELOG↔relatórios) + `python scripts/validate_ux_page.py examples/ux-page` (UX/acessibilidade mecânica sobre páginas HTML autocontidas, camada opcional) + o `test_command` do contrato, tudo verde localmente e no CI (`.github/workflows/validate.yml`, matriz dual-SO). Nenhum contrato é considerado concluído até passar o nível 1.
- **Nível 2 (opcional):** o gate CCDD real via o servidor MCP `ccdd-complexity` (`lint_task_contract`, `run_integration_gate`) sobre o export de `scripts/export_gate_contract.py`. Com o gate presente, sua config assinada tem precedência sobre o `budget` do frontmatter.

### Versionamento

O modelo usa **versionamento semântico** começando em `v1.0.0`. Veja [`CHANGELOG.md`](CHANGELOG.md) para o histórico de releases. Quando você instanciar este modelo com `init_project`, você herda uma base versionada que pode atualizar: o nó [`Upgrade de la plantilla`](knowledge/plantilla-upgrade.md) documenta o que é infraestrutura do modelo (atualizável a partir do upstream) e o que pertence ao seu projeto (seu, para manter ou modificar como preferir).