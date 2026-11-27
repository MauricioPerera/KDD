# Guías de validación local

[Índice de validación](../../knowledge/validacion.md).

## Preflight — diagnóstico local opt-in (NO es un gate)

`python scripts/preflight.py` corre los **19 gates de Nivel 1** más
`validate_attestation` (el local-only que CI nunca ve, porque
`.agents/logs/` está gitignorado) en dry-run contra el repo actual, y
reporta cuáles fallarían en una sola pasada — una línea por gate
(`PASS`/`FAIL`/`TIMEOUT`) + resumen `N/20`. Con `--contract <nombre>`
hace 3 chequeos acotados a un solo task contract: frontmatter, sello del
oráculo y `test_command` (resumen `N/3`). Exit 0/1; cero dependencias
(stdlib + módulos hermanos de `scripts/`, sin el SDK `mcp`).

En modo full, `validate_test_commands` tiene un timeout agregado calculado como
`max(300, suma_de_plazos_por_contrato + 30)` segundos; cada otro gate mantiene 120s. El
`test_command` individual de `--contract` mantiene 120s.

Esto **no es un gate nuevo**: Nivel 1 sigue siendo **19 gates** y el
conteo no cambia. Es diagnóstico opt-in, mismo estatus que
`benchmark_gates.py` — no corre en CI (CI ya ejecuta cada gate como paso
propio). Es la boca CLI de `run_all_level1` (la tool MCP que corre 19;
ver [mcp-server.md](../../knowledge/mcp-server.md)) y el único lugar donde los 20 gates
corren juntos, porque `validate_attestation` solo tiene sentido sobre
`.agents/logs/` local. Uso típico: correrlo **antes de delegar trabajo a
un agente**, para no mandarle un repo que ya rompe un gate. Ver
[preflight](../../knowledge/contracts/preflight.md).

Con `--agent`, cada gate en rojo arrastra la **receta de arreglo** de cada
rule-id que reportó (ver la sección siguiente). El flag no cambia el
veredicto ni el exit code: solo enriquece la salida.

## Recetas de arreglo por rule-id (`scripts/rule_hints.py`)

Los validadores dicen **qué** falló (`clave requerida ausente: type`), no
**qué hacer**. Un humano lo deduce leyendo el nodo OKF correspondiente; un
agente efímero, que llega en frío y no tiene ese contexto, itera a ciegas.
`scripts/rule_hints.py` es el mapa `rule-id → receta` que cierra ese hueco:

```
python scripts/rule_hints.py FM_TESTS_FROZEN   # una receta
python scripts/rule_hints.py --all             # todas
python scripts/rule_hints.py --json            # el mapa completo
python scripts/preflight.py --agent            # gates en rojo + su receta
```

Como dato es importable: `hint_for(rule_id)` devuelve la receta (o un
fallback genérico que apunta a este nodo, nunca vacío), y
`enrich(findings)` agrega `hint` a una lista de findings
`{file, level, rule, msg}` sin mutar la entrada.

**Contrato de una receta:** dice qué hacer, no repite el error; nombra el
archivo, la clave o el comando concreto; cabe en 1-3 líneas. La cobertura
la gatea `tests/test_rule_hints.py` en las **dos** direcciones — todo
rule-id que un validador pueda emitir debe tener receta, y ninguna receta
puede documentar un código que ningún validador emite. Sin ese gate el
mapa envejece en silencio, que es justo lo que venía a evitar.

Linaje: es el análogo de `tools/rule-hints.js` del proyecto hermano
[game-protocol](https://github.com/MauricioPerera/game-protocol), donde
cada hallazgo del linter viaja con su arreglo en el modo `--agent`. Ver
[el puente entre ambos](../../knowledge/game-data-bridge.md).

## Auditor de seals débiles — diagnóstico opt-in (NO es un gate)

`python scripts/audit_seals.py [contracts_dir] [--repo-root DIR] [--strict]`
es un auditor ADVISORY, stdlib puro y solo lectura (vía `ast`), que
detecta oráculos congelados que el sello (`tests_sha256`) certifica como
íntegros pero que **no pueden fallar**: sin asserts reales (`assert True`
no cuenta), sin funciones de test, o que jamás referencian al target. La
tesis: el sello garantiza la **integridad** del oráculo, no su **fuerza**;
detectar la ausencia es mecánico, juzgar la calidad de un assert es
mutation testing (fuera de alcance). Las 6 reglas: `WEAK_TESTS_MISSING`,
`WEAK_TESTS_EMPTY`, `WEAK_TESTS_UNPARSEABLE`, `WEAK_NO_TEST_FUNCTIONS`,
`WEAK_NO_ASSERTS`, `WEAK_TARGET_UNREFERENCED`.

Sin `--strict` SIEMPRE exit 0 (advisory, warnings); con `--strict`, exit 1
si hay findings. Esto **no es un gate nuevo**: Nivel 1 sigue siendo **19
gates** y el conteo no cambia. Mismo estatus opt-in que
`benchmark_gates.py` y `preflight.py` — no corre en CI, no está en
`GATE_SPECS`. Casos legítimos que NO marca: contratos auto-referenciales
(`target == tests`, como `agents-context-rule`) y tests no-Python (solo
chequeos textuales). Cierra la mitad diferida del feedback externo del
Contrato 32 ("help catch weak test seals early"). Ver
[seal-audit](../../knowledge/contracts/seal-audit.md).

## Auditor de `forbids` — diagnóstico opt-in (NO es un gate)

`python scripts/audit_forbids.py [contracts_dir] [--repo-root DIR] [--strict]`
compara el `forbids` **declarado** en cada contrato contra lo que está
efectivamente impedido. Hasta ahora nadie verificaba su contenido —
`tc_lint` solo avisa si la lista está vacía — así que un contrato podía
declarar `forbids: ['unsafe']` sobre un proyecto Rust que permite `unsafe`
sin que ningún gate lo notara: la prohibición era decorativa (hallazgo real
sobre el propio proyecto de prueba de esta plantilla).

Hay **un solo verificador**: `unsafe` en Rust. Se eligió porque es el único
donde la prohibición es comprobable de verdad — rustc la puede imponer sobre
el **crate entero**, no sobre un archivo. Se acepta cualquiera de las tres
vías equivalentes: `#![forbid(unsafe_code)]`/`#![deny(unsafe_code)]` en la
raíz del crate, `unsafe_code = "deny"|"forbid"` bajo `[lints.rust]` del
`Cargo.toml`, o herencia del workspace (`[lints] workspace = true` +
`[workspace.lints.rust]`). Con la denegación presente no reporta nada aunque
el target use `unsafe`: rustc rechaza la compilación, o sea que el fallo de
build **es** el enforcement.

Las 3 reglas: `FORBID_UNSAFE_PRESENT` (declara la prohibición y el target la
viola, sin denegación — regla **dura**), `FORBID_UNSAFE_UNENFORCED` (declarada
pero nada la impone a nivel compilador; hoy el target no la viola, mañana sí)
y `FORBID_UNVERIFIED` (no hay verificador para ese par capacidad/lenguaje).

Esa última regla es el punto: `network`, `subprocess` y `llm` **siguen siendo
declarativos** y el auditor lo dice en vez de callar, así que un `forbids` en
limpio deja de significar "todo verificado" y pasa a significar "esto
verificado, esto todavía no". `FORBID_UNVERIFIED` nunca cambia el exit code,
ni con `--strict` — es una limitación del auditor, no un incumplimiento.

Sin `--strict` SIEMPRE exit 0 (advisory); con `--strict`, exit 1 solo si hay
reglas duras. Esto **no es un gate nuevo**: Nivel 1 sigue siendo **19 gates**
y el conteo no cambia. Mismo estatus opt-in que `audit_seals.py` y
`preflight.py` — no corre en CI, no está en `GATE_SPECS` (agregarlo haría
crecer `LEVEL1_GATES` y rompería el oráculo congelado del preflight). Ver
[forbids-audit](../../knowledge/contracts/forbids-audit.md).

## Detalle de Nivel 1

### Catalogo de gates y controles locales

- `python scripts/validate_contracts.py knowledge/contracts` — valida frontmatter, secciones obligatorias y examples de cada contrato. La clave `tests_sha256` es **obligatoria**: contiene el SHA256 normalizado (LF) del archivo de tests, congelando el oráculo (un cambio legítimo al archivo de tests exige re-sellar el hash; el diff del sello hace visible el cambio en review). Para sellar un contrato nuevo: `python scripts/validate_contracts.py --hash <tests_path>` imprime el hash a copiar al frontmatter. Trade-off aceptado: en proyectos ya instanciados desde la plantilla, los contratos sin sello pasan de WARNING a ERROR al actualizar el validador — el mensaje de error nombra el comando de sellado.
- **Subclaves de `budget` verificadas por nombre (`FM_BUDGET_KEY` / `FM_BUDGET_VALUE`).** Las únicas válidas son las que el gate de Nivel 2 realmente LEE (`GLOBAL_MAX` de `tc_lint.py`): `cyclomatic_max`, `nesting_max`, `lines_max`, `params_max`, cada una con un entero positivo. El motivo es un fallo silencioso real: hasta esta versión la plantilla documentaba `max_cyclomatic_complexity`/`max_nesting_depth`, que el gate **nunca leyó** — el tope declarado en el contrato se descartaba y el gate caía a su config firmada, así que un `budget` estricto en el frontmatter no aplicaba nada y nadie lo notaba. Verificado: un contrato con `max_params: 1` y una firma de 5 parámetros pasaba el lint sin un solo error. Ahora ese caso es ERROR y el mensaje nombra el reemplazo canónico. Los **valores** siguen siendo informativos en Nivel 1 (los topes los enforce el Nivel 2, ver [precedencia](../../knowledge/validacion.md#precedencia-del-budget)); lo que Nivel 1 garantiza es que el nombre que escribiste es uno que el gate va a mirar. Trade-off aceptado, mismo patrón que `tests_sha256`: en proyectos ya instanciados, los contratos con los nombres viejos pasan a ERROR al actualizar el validador — el mensaje de error dice exactamente a qué renombrar.
- `python scripts/validate_specs.py specs` — valida que los contratos de ejecución de nivel proyecto tengan criterios de aceptación verificables por máquina, perímetro y condiciones de aborto (abierto vs. cerrado según `docs/reports/CONTRACT-NN-REPORT.md`).
- `python scripts/validate_completion.py` — compara specs cerrados, reportes y
  `CONTRACT-NN-EVIDENCE.json`. Un cierre nuevo exige checkboxes con ID marcados,
  evidencia para cada ID y un run de CI enlazado por el reporte. Los 33 pares
  historicos de `completion-legacy.json` se reconocen por digest exacto y se
  reportan como **SKIP**, nunca PASS; al modificarlos hay que migrarlos al
  formato nuevo. El reporte incluye una tabla por ID que debe coincidir con
  el manifiesto. El enlace al run no verifica por si solo su resultado remoto:
  `verify_completion_runs.py` consulta la API de GitHub en CI, exige un run
  anterior exitoso para el SHA declarado y rechaza cambios de codigo despues
  de ese run. Ver [garantias](../../knowledge/verification-guarantees.md#cierre-de-contratos-de-proyecto).
  En proyectos consumidores sin politica, la integracion reutilizable usa el
  repositorio de CI y cero excepciones historicas. Es un control de cierre de
  proyecto adicional al conjunto fijo de 19 gates de Nivel 1 de preflight.
- `python scripts/lint_ascii.py scripts` — exige ASCII en los literales string de `scripts/*.py` (docstrings excluidas; excepciones legítimas vía pragma `# ascii: allow` de línea o `# ascii-lint: skip-file` de módulo, declarado en el resumen).
- `python scripts/validate_rules.py <dir>` — gate de los [rule contracts](../../knowledge/rule-contract-spec.md) (reglas de negocio como datos): familias conocidas, golden sellado por hash y reproducción por el motor declarativo. Capa opcional: sin rule contracts, pasa con INFO.
- `python scripts/validate_skills.py skills .agents/skills` — gate de las skills de agente (infraestructura, no ejemplo): `SKILL.md` presente por skill, frontmatter parseable (mismo dialecto mini-YAML, coherencia fijada a 3 vías), `name` kebab-case e igual al directorio y único, `description` con largo en [50, 1024], cuerpo no vacío y enlaces relativos que resuelven (ignorando code spans/fences). Capa opcional: directorio ausente pasa con INFO.
- `python scripts/validate_changelog.py` — coherencia bidireccional CHANGELOG↔reportes: todo `docs/reports/CONTRACT-NN-REPORT.md` tiene su entrada `**Contract NN` con link (y viceversa, sin duplicados). Nacido del incidente real de v1.2.0 (entradas perdidas por un replace silencioso). Capa opcional: sin CHANGELOG o sin reportes pasa con INFO.
- `python scripts/validate_ux_page.py <dir>` — gate mecánico de UX/accesibilidad sobre páginas HTML autocontenidas (infraestructura, no ejemplo): balance de tags, completitud de i18n vía JSON embebido (`#i18n-data`), contraste WCAG sobre pares explícitos (`#ux-contrast-pairs`), guarda `prefers-reduced-motion`, IDs referenciados por JS. Severidad calibrada contra `google-labs-code/design.md`: referencias rotas = ERROR (bloquea), contraste/motion = WARNING (no bloquea). El juicio estético queda deliberadamente fuera — misma frontera que el dominio editorial. Capa opcional: sin páginas HTML, pasa con INFO.
- **Herramienta opt-in, no gate de este repo:** `python scripts/validate_commit_message.py <config.json> [--message <texto>|--file <ruta>|stdin]` — formato de mensaje de commit calibrado contra Conventional Commits + `commitlint`. NO corre en `.github/workflows/validate.yml` (el historial propio de KDD no sigue esta convención); es infraestructura de plantilla para que un proyecto instanciado la adopte en su propio hook `commit-msg` si quiere.
- `python scripts/validate_diagrams.py <dir>` — gate mecánico de diagramas Mermaid (infraestructura, no ejemplo; 4 tipos: `flowchart`/`graph`, `gantt`, `pie`, `journey`): parser propio en Python puro (sin `subprocess`/red/LLM, por `forbids`) para nodos/edges, verificados contra un `.diagram-contract.json` declarativo al lado de cada `.mmd`. Convención completa: [diagram-contract-spec](../../knowledge/diagram-contract-spec.md). Cobertura deliberadamente parcial (4 de los ~20 tipos de Mermaid); para el resto de los tipos de diagrama y fidelidad de parser real, ver el proyecto hermano `mermaid-gate` (Node.js, herramienta externa, fuera del alcance Nivel 1 de este repo por la misma razón que el gate CCDD real es Nivel 2). Capa opcional: sin diagramas, INFO; `.mmd` sin contrato, WARNING (no bloquea).
- `python scripts/validate_security_findings.py <dir>` (default `security/scan`) — gate de la Capa 3 de seguridad: valida un `findings.json` YA SELLADO (schemas y sellador vendorizados de [openai/codex-security](https://github.com/openai/codex-security)) contra `examples/rules/security-findings.rules.json` via el mismo motor declarativo de `validate_rules.py`. Ver [security_findings.md](../../knowledge/data_models/security_findings.md). Capa opcional: sin `findings.json`, INFO.
- Los siete scans opcionales de Capa 3 y `quality.json` aparecen en el
  resumen del job como **PASS**, **FAIL** o **SKIP**. PASS exige que el archivo
  de evidencia exista *y* que su validador haya terminado en success; la
  ausencia opcional es SKIP. Un consumidor del workflow reutilizable puede
  declarar `required_evidence: security,privacy,quality` (o un subconjunto de
  los nombres documentados en [optional-evidence](../../knowledge/contracts/optional-evidence.md));
  entonces la ausencia falla antes de ejecutar validadores. La accion
  compuesta acepta `required-evidence` para los siete scans y quality;
  `quality-approved-ref` debe ser un SHA completo cuando exista la politica.
  Al inicializar un proyecto, ambas entradas adaptan su workflow para
  exigir quality/product.json y una referencia revisada; la ausencia falla.
  Ver [calidad desde el arranque](../../knowledge/bootstrap-product-quality-ci.md).
- `python scripts/validate_compliance_findings.py <dir>` (default `compliance/scan`) — gate de la Capa 3 de compliance/licencias: valida un `findings.json` de compatibilidad de licencias de dependencias (nativo, sin vendoring) contra `examples/rules/compliance-findings.rules.json` via el mismo motor declarativo. Ver [compliance_findings.md](../../knowledge/data_models/compliance_findings.md). Capa opcional: sin `findings.json`, INFO.
- **Diagnóstico opcional (no gate):** `python scripts/benchmark_gates.py` mide los 19 gates de nivel 1 + la suite (min/mediana/max por gate, 2 pasadas crudas de la suite) para saber si el CI se está volviendo lento a medida que crecen los contratos. No corre en `.github/workflows/validate.yml` — es herramienta de mantenimiento, no un check de corrección.
- La clave **`touch_only`** del frontmatter (obligatoria) declara el perímetro de la delegación como DATO — lista de rutas/patrones `fnmatch` repo-relativos. `validate_contracts` la exige y verifica que el `target` esté cubierto y que el oráculo (`tests`) quede FUERA (salvo `tests == target`). En verificación, el PM corre `git diff --name-only ... | python scripts/validate_perimeter.py <contrato>`: cualquier archivo del dev fuera del perímetro rompe con `OUT_OF_PERIMETER` (y tocar el oráculo, con `TESTS_TOUCHED`). El gate de perímetro NO es paso de CI del repo (un commit mergeado mezcla legítimamente archivos del PM); su oráculo corre en la suite y los checks estructurales corren vía `validate_contracts`.
- `python scripts/validate_test_commands.py <contracts_dir> <repo_root>` — corre el `test_command` de CADA contrato de `<contracts_dir>` y falla si algun exit code no es 0. Uno de dos gates de Nivel 1 cuyo `forbids` no incluye `subprocess` (el otro es `mcp-gate-dispatch`): correr un comando arbitrario es literalmente su intent (ver [test-command-gate](../../knowledge/contracts/test-command-gate.md), seccion "Por que este gate rompe la convencion forbids: subprocess"). Antes de este gate, la linea de arriba ("el `test_command` debe terminar en verde") era una regla escrita pero NO mecanicamente verificada por ningun gate de Nivel 1 — un contrato podia pasar los otros 9 gates con un `test_command` roto y nadie lo notaba salvo corrida manual. `TEMPLATE-*.md` se excluye (no es un contrato real). Timeout de 180s por defecto por comando, configurable con `--timeout`, para no confundir una suite lenta conocida con un fallo; un proceso colgado sigue fallando. Esta incluido en `benchmark_gates.py`, cuya lista de gates deriva de `LEVEL1_GATES`.

### Auditoria del cambio y controles de codigo

- `python scripts/scan_secrets.py <dir1> [<dir2> ...]` (default `src`) — escaneo determinista (regex stdlib) de credenciales filtradas por prefijo de proveedor conocido (AWS `AKIA...`, GitHub `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`, Slack `xox[baprs]-`, Google `AIza...`, Stripe `sk_live_`/`pk_live_`) y bloques `-----BEGIN ... PRIVATE KEY-----`. Deliberadamente SIN deteccion de alta entropia generica (rompería contra los `tests_sha256` de 64 hex chars que ya viven en este repo). El default es solo `src` (no `src tests`) precisamente porque `tests/test_scan_secrets.py`, el oraculo del propio gate, se hereda en todo proyecto instanciado del template (no esta en el MANIFEST de `scripts/init_project.py`) y contiene fixtures con la FORMA exacta de los patrones — se auto-detectaria como leak si `tests` fuera parte del default. En el CI de ESTE repo corre como `python scripts/scan_secrets.py src`. **La cobertura es la lista `DEFAULT_EXTENSIONS`: lo que no esta ahi no se mira.** Cubre los lenguajes con backend en el gate (`.py`, `.rs`, `.go`, `.java`, `.cs`, `.php`, `.rb`, `.kt`, `.c`/`.cpp`, `.swift`, `.js`/`.ts`…) mas config/scripts (`.toml`, `.yaml`, `.env`, `.sh`, `.tf`…). Hasta la version anterior la lista era solo `('.py','.js','.ts','.md','.json')`, asi que **en un proyecto Rust/Go/Java el gate escaneaba CERO archivos y salia 0** — un gate de seguridad reportando verde sin haber leido nada; el mismo secreto se detectaba en un `.py` y se ignoraba en un `.rs`. Por eso ahora, si un directorio tiene archivos y ninguno matchea, emite `SECRETS_NO_FILES_SCANNED` (WARNING, no rompe el build): el modo de fallo peligroso de un escaner de secretos no es reportar de mas, es el verde silencioso. Ver [secret-scan-gate](../../knowledge/contracts/secret-scan-gate.md).

Enforcement local opt-in de budgets Python: `python scripts/validate_budgets.py knowledge/contracts --repo-root . --contract <task>` mide el target de una tarea contra `cyclomatic_max`, `nesting_max`, `lines_max` y `params_max`. Exit 1 significa exceso. La ejecución global, sin `--contract`, es diagnóstica para revelar la deuda de budgets históricos sin convertirla silenciosamente en un gate de CI. Los targets no Python se omiten explícitamente hasta incorporar un medidor equivalente. Este paso no sustituye al gate CCDD multi-lenguaje; permite avanzar con una comprobación determinista aunque no esté disponible el servidor MCP.

El CI nativo de KDD audita tambien las funciones Python nuevas y modificadas
de objetivos con contrato. Usa los topes del commit base para contratos
preexistentes y bloquea excesos nuevos o mayores. Cada medida identifica
contrato, objetivo, funcion y metrica. Ver
[presupuestos del diff](../../knowledge/contracts/changed-python-budgets.md).

En Ubuntu y Windows, la primera pasada nativa mide lineas y ramas Python de
`scripts`, `src`, `site` y `tools/kdd-adoption`, incluidos los procesos
aislados. El informe JSON por SO, SHA e intento conserva los denominadores
y se publica como artefacto. La segunda pasada conserva la ejecucion normal.
Ver [cobertura medida](../../knowledge/contracts/ci-measured-coverage.md).

Auditoria opt-in del diff de implementacion: `python scripts/validate_change_contract.py
--contract knowledge/contracts/<task>.md --base-ref <SHA-aprobado>
--head-ref <SHA-candidato>` lee el contrato desde el commit base y compara
el diff Git real con `touch_only`; para un target Python cambiado comprueba
los imports externos **nuevos** contra `deps_allowed` y aplica su `budget` al
codigo del commit candidato. Los imports externos existentes en el base no
bloquean una migracion. Los nombres en `deps_allowed` se interpretan como
raices de import. Los adaptadores Tree-sitter fijados en
`requirements-change-audit.txt` hacen el equivalente para
JavaScript/JSX, TypeScript/TSX, Go y Rust: extraen imports estaticos, comparan
`package.json`, `go.mod` o `Cargo.toml` y miden funciones contra los cuatro
topes del contrato. Tambien revisan dependencias si cambia solo el manifiesto
asociado, aunque el target permanezca intacto. Se necesita el manifiesto mas
cercano al target en cada commit; cambiar un manifiesto padre ignorado no
activa el chequeo, y agregar o quitar el mas cercano compara las dependencias
efectivas antes y despues. El guard confiable protege
`requirements-change-audit.txt` para que un PR no cambie los parsers que CI
instala antes de validar. Las decisiones de switch/select en Go y while/for en
Rust cuentan en los presupuestos. Las
ramas case de un switch/select Go no duplican su nivel de nesting. Las
dependencias transitivas no se resuelven; imports dinamicos y macros Rust
opacas producen hallazgos duros. La metrica de estos adaptadores es
determinista sobre el AST y no pretende equivalencia exacta con CCDD. Otros
lenguajes emiten `CHECK_UNSUPPORTED`. Ver
[contrato del auditor](../../knowledge/contracts/change-contract-audit.md). En el workflow
reutilizable se activa con `change_contract_path`; usa el mismo
`approved_baseline_ref` independiente que valida contratos y oraculos. Debe
activarse para PRs de implementacion cuya diferencia desde ese baseline sea
la tarea declarada; un PR que agregue otros archivos necesita otro contrato o
un alcance revisado. Sin esa entrada el paso informa SKIP.

## Inventario historico de 49 excesos Python

```text
ERROR [BUDGET_CYCLOMATIC] assemble-context.md:_validate_contract: cyclomatic_max=39 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] assemble-context.md:_assemble_okf_nodes: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] assemble-context.md:assemble: cyclomatic_max=28 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] assemble-context.md:assemble: nesting_max=6 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] attestation-gate.md:validate_report: cyclomatic_max=19 excede cyclomatic_max=16
ERROR [BUDGET_NESTING] attestation-gate.md:validate_report: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] benchmark-gates.md:main: cyclomatic_max=15 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] benchmark-gates.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] changelog-gate.md:validate_changelog: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] check-agent-wiring.md:check_agent_wiring: cyclomatic_max=27 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] check-graph.md:find_graph_cycles: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] commit-message-gate.md:main: cyclomatic_max=13 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] commit-message-gate.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:parse_gantt: cyclomatic_max=17 excede cyclomatic_max=14
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:_validate_flowchart: cyclomatic_max=17 excede cyclomatic_max=14
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:_validate_gantt: cyclomatic_max=15 excede cyclomatic_max=14
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:_validate_journey: cyclomatic_max=17 excede cyclomatic_max=14
ERROR [BUDGET_NESTING] diagram-gate.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] evidence-hardening.md:main: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] forbids-audit.md:audit_contract: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] forbids-audit.md:main: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_NESTING] forbids-audit.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_NESTING] lint-ascii.md:_find_docstrings: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] lint-ascii.md:_lint_file: cyclomatic_max=15 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] lint-ascii.md:_lint_file: nesting_max=6 excede nesting_max=4
ERROR [BUDGET_PARAMS] pages-build.md:update_landing: params_max=5 excede params_max=4
ERROR [BUDGET_CYCLOMATIC] pages-build.md:build_pages: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] perimeter-gate.md:_parse_block: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] rules-gate.md:_validate_golden_forma: cyclomatic_max=20 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] rules-gate.md:validate_rules: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] seal-audit.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] skills-gate.md:_parse_block: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] skills-gate.md:validate_skills: cyclomatic_max=27 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] ux-page-gate.md:_check_contrast: cyclomatic_max=17 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] validate-article.md:validate_article: cyclomatic_max=34 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-article.md:validate_article: nesting_max=6 excede nesting_max=3
ERROR [BUDGET_CYCLOMATIC] validate-okf.md:_parse_block: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] validate-okf.md:_validate_frontmatter: cyclomatic_max=16 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-okf.md:_validate_frontmatter: nesting_max=6 excede nesting_max=4
ERROR [BUDGET_NESTING] validate-okf.md:_reachable_from_index: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-payment-limit.md:validate_payment_limit: cyclomatic_max=13 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-payment-limit.md:validate_payment_limit: nesting_max=4 excede nesting_max=3
ERROR [BUDGET_CYCLOMATIC] validate-rules.md:_check_type: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-rules.md:_check_type: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-rules.md:_check_bounds: cyclomatic_max=15 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-rules.md:_check_bounds: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-rules.md:evaluate: cyclomatic_max=38 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-rules.md:evaluate: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-specs.md:validate_file: cyclomatic_max=13 excede cyclomatic_max=10
```

## Diagnostico del tiempo de CI en octubre de 2026

Medición del árbol `af680c1fd251b080c154ab2eacf62d74434a4451`. El [nodo de diagnóstico](../../knowledge/ci-diagnostico-2026-10.md) conserva su alcance y sus enlaces.

### Medicion en GitHub Actions

El [run 40648566045](https://github.com/MauricioPerera/KDD/actions/runs/40648566045)
paso para ese arbol. Los jobs de validacion y Board corrieron en Ubuntu y
Windows; la suite principal ejecuto dos pasadas por sistema con 1.636 IDs.
Cada pasada declaro 9 skips en Windows y 10 en Ubuntu; esos IDs incluyen
casos omitidos y no equivalen a 1.636 casos aprobados.

| Medida | Windows | Ubuntu |
| --- | ---: | ---: |
| Job validate | 37 min 56 s | 7 min 2 s |
| Comandos de contratos | 17 min 53 s | 2 min 30 s |
| Suite, primera pasada | 9 min 26 s | 2 min 4 s |
| Suite, segunda pasada | 9 min 12 s | 2 min 3 s |
| Job Board | 1 min 11 s | 23 s |

En Windows, los tres pasos consecutivos de contratos y suites sumaron
36 min 31 s, alrededor del 96 % del job. Son tiempos de pared por paso, no
la suma de los procesos que trabajan en paralelo. Esta muestra no demuestra
por si sola la causa de la diferencia entre sistemas.

El gate agrupo 121 contratos en 119 comandos unicos dentro de su invocacion.
Un cruce estatico entre selectores de contratos e inventario detecto 1.483 IDs
potencialmente compartidos con las suites. No acredita que todos se ejecutaran
en ambos contextos ni que sus garantias sean equivalentes; los skips y la copia
inicializada deben analizarse por separado.
En Windows, `init-project` se ejecuto en exclusiva antes del pool de cuatro
workers; sus 16 casos informaron 415,209 s de unittest. Ubuntu informo
121,621 s para esos casos, sin la misma exclusividad. Ese tiempo incluye la
creacion y validacion de un proyecto real y la suite en su copia. La
[exclusividad y limites de recursos](../../knowledge/contracts/ci-contract-resources.md)
responden a timeouts observados; no se ha demostrado que retirarlos sea seguro.

Para ese mismo run, la salida de unittest permite atribuir tiempos parciales a
110 contratos por sistema, pero no reconstruir todos los intervalos de los
119 procesos: el resultado del gate se imprime al terminar el lote y sus
reportes temporales por comando no se publicaron. Los tiempos de unittest no
incluyen necesariamente todo el proceso. No es posible identificar el camino
critico completo de ese gate con esos datos.

### Perfil local de la copia inicializada

Una ejecucion local Windows con Python 3.11.15, parsers fijados y actionlint
verificado paso los 16 casos de `init-project` en 379,459 s. La suite de la
copia tardo 370,348 s: 120 modulos, 1.530 IDs esperados y ejecutados, 73 skips
declarados y cero errores. Esta copia tiene su propio inventario; no equivale
a una de las dos pasadas de la plantilla original. Los skips incluyen casos
de plantilla que no aplican y SDK o dependencias ausentes de ese entorno.

Otra ejecucion local envolvio el runner para registrar los intervalos de sus
120 workers. De 391,484 s entre el primer inicio y el ultimo final, cuatro
workers estuvieron activos 384,500 s. Tras el inicio del ultimo modulo
restaron 7,781 s. El envoltorio llamo `run_suite` directamente, sin el proceso
supervisor habitual, y agrego escritura de diagnostico. La ocupacion de
workers no mide uso de CPU ni de disco; es una muestra local, no CI remoto.

En esta muestra, la falta de modulos disponibles para repartir no explica una
gran cola final. Reordenarlos podria cambiar la contencion y los tiempos: un
modelo con duraciones fijas no demuestra ahorro. La instrumentacion y las
cargas locales impiden extrapolar sus porcentajes a los runners de GitHub.

Dos intentos locales anteriores fallaron por preparacion del entorno y
fixtures: uno carecia de actionlint y otro de los parsers requeridos. Se
conservaron como fallos de diagnostico, no como pruebas verdes ni como fallos
del CI de referencia. Los reportes y trazas crudas de esta investigacion
quedaron en `.agents/logs/`, que es local e ignorado por Git; este nodo no
afirma que esten disponibles en un clon nuevo.

### Costes de operaciones Git y lectura de tareas

Una traza local del piloto de cuatro tareas registro 2.145 procesos Git; 22
llamadas a `git log` coincidieron con la lectura de historiales bajo el arbol
de Board. Una consulta de historial de un fixture concreto lanzo 10 procesos
Git por CLI y 7 mediante la llamada directa; devolvieron las mismas cuatro
entradas con `main` estable. No se midio un ahorro del job completo.

La CLI lee las tareas antes de solicitar el historial, que vuelve a comprobar
su existencia. En un clon aislado, al cambiar `main` entre lecturas, los dos
caminos produjeron errores distintos: `TASK_MISSING` y `TASK_GIT`. El ensayo
no ejecuto Board HTTP. Una modificacion debe definir primero la semantica de
errores y carreras y preservar la frescura de refs y la auditoria historica.
Ver [presupuesto de lectura de main](../../knowledge/contracts/task-main-read-budget.md) y
[coste de lectura del historial](../../knowledge/task-history-read-cost.md).

### Preguntas abiertas y siguiente medicion

1. Registrar por comando y por worker inicio, fin, veredicto y contexto para
   identificar el camino critico real, sin interpretar la suma de procesos
   concurrentes como tiempo de pared. La instrumentacion necesita validar
   su coste y confiabilidad antes de afectar el CI.
2. Perfilar las fases y recursos de las integraciones mas largas, manteniendo
   las pruebas reales, las esperas de terminacion y sus limites. Ni el coste
   local de una copia ni el numero de procesos prueba una causa del CI remoto.
3. Comparar varias muestras equivalentes antes y despues: SHA, evento,
   intento, SO, versiones, inventarios, skips y fallos; reportar job critico,
   tiempo total y suma de jobs por separado. No atribuir causalidad a
   diferencias de runner, cache o cantidad de pruebas no controladas.
4. Para cualquier cambio futuro, definir primero contratos y oraculos,
   preservar Ubuntu/Windows, cobertura y dos pasadas, y seguir la
   [aprobacion de calidad](../../knowledge/quality-approval.md) y el
   [protocolo de medicion](../../knowledge/ci-runtime.md). Esta investigacion no autoriza
   cambios de runtime, protecciones ni reutilizacion de resultados entre
   pasadas.
