---
type: 'Concept'
title: 'Validación de contratos (niveles 1 y 2)'
description: 'Nodo canónico: los dos niveles de validación de contratos, el gate multi-lenguaje, el export para el gate, la precedencia del budget y el ciclo de vida draft→verified.'
tags: ['ccdd', 'validacion', 'gate', 'reference']
---

# Validación de contratos — nodo canónico

Única fuente de verdad sobre cómo se valida un task contract en esta plantilla. El README, [.agents/AGENTS.md](../.agents/AGENTS.md) y la skill `kdd-okf-ccdd-hybrid` enlazan aquí en lugar de duplicar este contenido (regla §4 de [OKF-SPEC](./OKF-SPEC.md)).

## Nivel 1 — Incluido y obligatorio (local + CI)

- `python scripts/validate_contracts.py knowledge/contracts` — valida frontmatter, secciones obligatorias y examples de cada contrato. La clave `tests_sha256` es **obligatoria**: contiene el SHA256 normalizado (LF) del archivo de tests, congelando el oráculo (un cambio legítimo al archivo de tests exige re-sellar el hash; el diff del sello hace visible el cambio en review). Para sellar un contrato nuevo: `python scripts/validate_contracts.py --hash <tests_path>` imprime el hash a copiar al frontmatter. Trade-off aceptado: en proyectos ya instanciados desde la plantilla, los contratos sin sello pasan de WARNING a ERROR al actualizar el validador — el mensaje de error nombra el comando de sellado.
- `python scripts/validate_specs.py specs` — valida que los contratos de ejecución de nivel proyecto tengan criterios de aceptación verificables por máquina, perímetro y condiciones de aborto (abierto vs. cerrado según `docs/reports/CONTRACT-NN-REPORT.md`).
- `python scripts/lint_ascii.py scripts` — exige ASCII en los literales string de `scripts/*.py` (docstrings excluidas; excepciones legítimas vía pragma `# ascii: allow` de línea o `# ascii-lint: skip-file` de módulo, declarado en el resumen).
- `python scripts/validate_rules.py <dir>` — gate de los [rule contracts](./rule-contract-spec.md) (reglas de negocio como datos): familias conocidas, golden sellado por hash y reproducción por el motor declarativo. Capa opcional: sin rule contracts, pasa con INFO.
- `python scripts/validate_skills.py skills .agents/skills` — gate de las skills de agente (infraestructura, no ejemplo): `SKILL.md` presente por skill, frontmatter parseable (mismo dialecto mini-YAML, coherencia fijada a 3 vías), `name` kebab-case e igual al directorio y único, `description` con largo en [50, 1024], cuerpo no vacío y enlaces relativos que resuelven (ignorando code spans/fences). Capa opcional: directorio ausente pasa con INFO.
- `python scripts/validate_changelog.py` — coherencia bidireccional CHANGELOG↔reportes: todo `docs/reports/CONTRACT-NN-REPORT.md` tiene su entrada `**Contract NN` con link (y viceversa, sin duplicados). Nacido del incidente real de v1.2.0 (entradas perdidas por un replace silencioso). Capa opcional: sin CHANGELOG o sin reportes pasa con INFO.
- `python scripts/validate_ux_page.py <dir>` — gate mecánico de UX/accesibilidad sobre páginas HTML autocontenidas (infraestructura, no ejemplo): balance de tags, completitud de i18n vía JSON embebido (`#i18n-data`), contraste WCAG sobre pares explícitos (`#ux-contrast-pairs`), guarda `prefers-reduced-motion`, IDs referenciados por JS. Severidad calibrada contra `google-labs-code/design.md`: referencias rotas = ERROR (bloquea), contraste/motion = WARNING (no bloquea). El juicio estético queda deliberadamente fuera — misma frontera que el dominio editorial. Capa opcional: sin páginas HTML, pasa con INFO.
- **Herramienta opt-in, no gate de este repo:** `python scripts/validate_commit_message.py <config.json> [--message <texto>|--file <ruta>|stdin]` — formato de mensaje de commit calibrado contra Conventional Commits + `commitlint`. NO corre en `.github/workflows/validate.yml` (el historial propio de KDD no sigue esta convención); es infraestructura de plantilla para que un proyecto instanciado la adopte en su propio hook `commit-msg` si quiere.
- **Diagnóstico opcional (no gate):** `python scripts/benchmark_gates.py` mide los 8 gates de nivel 1 + la suite (min/mediana/max por gate, 2 pasadas crudas de la suite) para saber si el CI se está volviendo lento a medida que crecen los contratos. No corre en `.github/workflows/validate.yml` — es herramienta de mantenimiento, no un check de corrección.
- La clave **`touch_only`** del frontmatter (obligatoria) declara el perímetro de la delegación como DATO — lista de rutas/patrones `fnmatch` repo-relativos. `validate_contracts` la exige y verifica que el `target` esté cubierto y que el oráculo (`tests`) quede FUERA (salvo `tests == target`). En verificación, el PM corre `git diff --name-only ... | python scripts/validate_perimeter.py <contrato>`: cualquier archivo del dev fuera del perímetro rompe con `OUT_OF_PERIMETER` (y tocar el oráculo, con `TESTS_TOUCHED`). El gate de perímetro NO es paso de CI del repo (un commit mergeado mezcla legítimamente archivos del PM); su oráculo corre en la suite y los checks estructurales corren vía `validate_contracts`.
- El `test_command` declarado en el frontmatter del contrato — debe terminar en verde.

Todos corren localmente y en CI (`.github/workflows/validate.yml`, matriz `ubuntu-latest` + `windows-latest`, que además valida los nodos OKF y corre la suite dos veces — dos corridas idénticas ≈ sin flaky). **Ningún contrato se considera terminado hasta que pase el nivel 1.**

## Nivel 2 — Opcional (si el entorno del agente lo tiene)

Si el agente dispone del servidor MCP `ccdd-complexity`, el gate CCDD real se invoca con sus tools `lint_task_contract` (lint del contrato) y `run_integration_gate` (gate de complejidad/integración). Si no está disponible, el nivel 1 es suficiente para considerar un contrato válido.

### Gate multi-lenguaje

- **Python** tiene un parser de firma nativo completo (validado estrictamente); es el único lenguaje con parsing de firma completo.
- **Otros lenguajes soportados** — JavaScript entre ellos, con cobertura de `measure_complexity` que además incluye TS/TSX/JS/Rust/Go/Java/C#/PHP/Ruby/Kotlin/C/Swift/C++ a la fecha (13 backends tree-sitter + Python nativo; la lista no es exhaustiva ni fija: consulta el gate real para la lista vigente) — enrutan a un backend tree-sitter que aplica el mismo budget de complejidad (cyclomatic/nesting/params) que Python.
- El `test_command` declarado en el contrato se corre **verbatim** (el gate ejecuta el comando declarado, con `cwd` = directorio del target). Los tests deben ser auto-ejecutables por ese comando; para JavaScript esto implica ESM (`.mjs` o `"type": "module"` en `package.json`) con un `test_command` como `"node --test <ruta>"`.
- Con `language` distinto de python, la `signature` se valida por **aridad genérica** (cantidad de parámetros), no con un parser nativo de ese lenguaje.
- `scan_dependencies` razona en clave Python (imports/stdlib) y NO debe usarse como parte del gate para lenguajes no-Python.

### Export para el gate

El gate se corre sobre el **export** generado por `scripts/export_gate_contract.py` (normalización ASCII + `target`/`tests` reescritos relativos al export): `lint_task_contract` recibe el texto del export + tests, y `run_integration_gate` recibe la ruta del export en disco. Por defecto el export se escribe en la raíz del repo como `<task>.gate.md` (gitignorado vía `*.gate.md`) para que las rutas reescritas no contengan `..`, como exige el gate real (`tc-tests-frozen`).

## Precedencia del budget

- **Con gate CCDD disponible (nivel 2):** la config firmada por el gate manda. El `budget` del frontmatter solo puede ser **<=** los topes firmados; ante cualquier conflicto gana la config firmada del gate.
- **Sin gate (solo nivel 1):** el `budget` del contrato es declarativo/informativo. El validador incluido solo verifica su **presencia** en el frontmatter; no aplica (enforce) los topes.

## Ciclo de vida del contrato

1. **draft** — contrato redactado en `knowledge/contracts/<task>.md`.
2. **validated** — validador de nivel 1 (y `lint_task_contract` si hay gate) en verde.
3. **implemented** — `test_command` del contrato en verde.
4. **verified** — la salida **REAL** de los comandos (validador + `test_command`, y gate si corre) se pega en `.agents/logs/<task>-REPORT.md`. Ese directorio está gitignorado a propósito: es evidencia local, no parte del repo.
