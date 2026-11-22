---
type: 'Concept'
title: 'Validación de contratos (niveles 1 y 2)'
description: 'Nodo canónico: los dos niveles de validación de contratos, el gate multi-lenguaje, el export para el gate, la precedencia del budget y el ciclo de vida draft→verified.'
tags: ['ccdd', 'validacion', 'gate', 'reference']
---

# Validación de contratos — nodo canónico

Única fuente de verdad sobre cómo se valida un task contract en esta plantilla. El README, [.agents/AGENTS.md](../.agents/AGENTS.md) y la skill `kdd-okf-ccdd-hybrid` enlazan aquí en lugar de duplicar este contenido (regla §4 de [OKF-SPEC](./OKF-SPEC.md)).

## Nivel 1 — Incluido y obligatorio (local + CI)

La [extension de tiempo total del CI](ci-runtime.md) conserva los19 gates,
Ubuntu/Windows y las dos pasadas completas. Sustituye el mecanismo serial
de suite por un runner auditable por IDs, con procesos acotados solo bajo
opt-in y default serial para consumidores. Sus contratos y oraculos deben
tener baseline revisado antes de activar ese mecanismo.

La [ejecucion confiable](ci-audit-remediation.md) extrae el runtime revisado
fuera del checkout y conserva reportes nuevos por pasada. La publicacion de
[Pages](pages-ci-inventory.md) consume sus inventarios y los compara con un
discovery estricto del mismo SHA. Es una comprobacion de publicacion;
el catalogo de Nivel 1 sigue teniendo 19 gates.

La migracion de behavior agrega `validate_behavior` al catalogo compartido: 19
gates de Nivel 1 y 20 en preflight contando la atestacion local. Se actualizaron
los oraculos de MCP/preflight y sus sellos como cambio de contrato revisable.
`python scripts/validate_behavior.py behavior` valida el esquema sin ejecutar
candidatos; la ejecucion sigue siendo opt-in. Ver [behavior](behavior-contract-spec.md).

El [catálogo de gates y controles locales](../docs/reports/ARCHIVO-VALIDACION.md#catalogo-de-gates-y-controles-locales) describe los comandos y su alcance. `validate_contracts.py` exige `tests_sha256` y `touch_only`. `validate_test_commands.py` ejecuta el comando de cada contrato con su plazo individual.

El perfil `standard` también corre ese gate: un producto roto ya no queda en
verde porque sólo pasó la suite heredada. Por diseño, `standard` y `strict`
validan primero los contratos y comparan todos los contratos/oráculos con
`--approved-ref <SHA>` antes de ejecutar la suite heredada o los
`test_command` de cada contrato. La referencia se exige como SHA completo;
no se deduce de `HEAD`. En el CI de este repositorio, `.github/workflows/validate.yml`
comprueba la referencia antes de ejecutar los `test_command` y la suite del PR.
El modo nativo selecciona las referencias revisadas desde
`KDD_APPROVAL_REGISTRY`, bajo el árbol Git exacto del candidato; sigue el
[registro externo](approval-registry.md). El workflow reutilizable admite
el input `approval_registry` o referencias explícitas mediante
`approved_baseline_ref` y `quality_approved_ref`, sin mezclar ambos modos.
El selector exporta `KDD_APPROVED_BASELINE_REF` y `KDD_QUALITY_APPROVED_REF`
para los pasos posteriores; las variables globales antiguas no son un fallback.
Sin una aprobación aplicable falla. No usa el SHA de la rama base ni HEAD
como aprobación implícita. El check independiente
`trusted-pr-gate` lee el merge propuesto desde el código de `main` y bloquea
cambios a los workflows o validadores protegidos; debe configurarse como
obligatorio en la protección de rama de cada repositorio que adopte este
control. La clasificación de pruebas por producto o infraestructura aparece
en el reporte del gate; `SKIP` significa ausencia de evidencia y nunca se
suma a `PASS`.
Consulta el [detalle de presupuestos, cobertura y perímetro](../docs/reports/ARCHIVO-VALIDACION.md#auditoria-del-cambio-y-controles-de-codigo), el [contrato del auditor](contracts/change-contract-audit.md) y el [alcance del escaneo de secretos](contracts/secret-scan-gate.md).

Todos corren localmente y en CI (`.github/workflows/validate.yml`, matriz `ubuntu-latest` + `windows-latest`, que además valida los nodos OKF y corre la suite dos veces — dos corridas son una comprobacion basica de repetibilidad; no prueban ausencia de flaky). El caso costoso de post-init se ejecuta una vez dentro del `test_command` de su contrato y se omite en las dos pasadas generales mediante `KDD_SKIP_INIT_POST_APPLY_SUITE=1`; los demás tests siguen corriendo dos veces. **Ningún contrato se considera terminado hasta que pase el nivel 1.**

## Preflight — diagnóstico local opt-in (NO es un gate)

[Guía y uso](contracts/preflight.md).

## Recetas de arreglo por rule-id (`scripts/rule_hints.py`)

[Guía y uso](../docs/reports/ARCHIVO-VALIDACION.md#recetas-de-arreglo-por-rule-id-scriptsrule_hintspy).

## Auditor de seals débiles — diagnóstico opt-in (NO es un gate)

[Guía y uso](contracts/seal-audit.md).

## Auditor de `forbids` — diagnóstico opt-in (NO es un gate)

[Guía y uso](contracts/forbids-audit.md).

## Nivel 2 — Opcional (si el entorno del agente lo tiene)

El motor CCDD puede usarse por [integracion nativa](./native-level2.md), sin MCP,
o mediante el servidor MCP `ccdd-complexity` con `lint_task_contract` y
`run_integration_gate`. El perfil nativo inicial cubre funciones Python y dispone
de setup reproducible por commit, timeout y evidencia JSON; consultar su alcance
antes de elegirlo. Si el proyecto exige Nivel 2, su ausencia o error bloquea la
verificacion: Nivel 1 no lo sustituye. Si no se exige Nivel 2, Nivel 1 sigue siendo
suficiente para validez estructural, sin afirmar complejidad verificada.

### Gate multi-lenguaje

- **Python** tiene un parser de firma nativo completo (validado estrictamente); es el único lenguaje con parsing de firma completo.
- **Otros lenguajes soportados** — JavaScript entre ellos, con cobertura de `measure_complexity` que además incluye TS/TSX/JS/Rust/Go/Java/C#/PHP/Ruby/Kotlin/C/Swift/C++ a la fecha (13 backends tree-sitter + Python nativo; la lista no es exhaustiva ni fija: consulta el gate real para la lista vigente) — enrutan a un backend tree-sitter que aplica el mismo budget de complejidad (cyclomatic/nesting/params) que Python.
- El `test_command` declarado en el contrato se corre **verbatim** (el gate ejecuta el comando declarado, con `cwd` = directorio del target). Los tests deben ser auto-ejecutables por ese comando; para JavaScript esto implica ESM (`.mjs` o `"type": "module"` en `package.json`) con un `test_command` como `"node --test <ruta>"`.
- Con `language` distinto de python, la `signature` se valida por **parser tree-sitter nativo** (nombre + nombres de parámetros en orden, tipos ignorados) cuando la gramática de ese lenguaje está instalada; si no lo está (dependencia opcional ausente), degrada a **aridad genérica** (solo cantidad de parámetros) con el warning `tc-signature-generic`, nunca falla en silencio.
- `scan_dependencies` razona en clave Python (imports/stdlib) y NO debe usarse como parte del gate para lenguajes no-Python.
- **Punto ciego de macros / DSL embebidos (límite REAL de la garantía).** El backend tree-sitter mide el árbol sintáctico del lenguaje anfitrión, y el cuerpo de una invocación de macro es para esa gramática un **token-tree opaco**: la lógica que vive adentro no se recorre, así que **no suma complejidad**. Medido sobre la misma lógica (cuatro `if` anidados) en Rust:

  | dónde vive la lógica | cyclomatic | nesting |
  |---|---|---|
  | código normal | 5 | 4 |
  | idéntica, dentro de `view! { … }` | **1** | **0** |
  | `for` normal | 2 | 1 |
  | `for` dentro de `view! { … }` | **1** | **0** |

  Una función cuya lógica entera vive en un macro **mide como si estuviera vacía**, y `measure_complexity` sobre código real de un framework de este tipo devuelve `findings: []`. Consecuencia práctica: en proyectos con DSL embebido pesado (Rust con `view!`/`html!`, JSX-en-macro, etc.) el budget de complejidad cubre el pegamento, no el DSL — y ahí es justamente donde suele estar la lógica. **No es un bug del backend**: medir dentro del macro exigiría expandirlo (`cargo expand`, compilación real) o un parser por DSL, las dos cosas fuera del alcance de un gate estático, determinista y sin subprocess. Se documenta en vez de disimularse: si tu proyecto es así, el budget te está diciendo menos de lo que parece, y la cobertura real la dan el oráculo congelado y el lint del lenguaje (ver el gate de `clippy`), no la métrica.
- **Costo real de un lenguaje no-Python compilado (ej. Rust):** la lógica del gate (métricas + firma) es sub-milisegundo, igual que Python — el parser cambia, el costo no. El costo real está en el `test_command`/lint del proyecto: para Rust, `cargo clippy` en frío (checkout limpio, sin caché de compilación) puede tardar del orden del minuto; con caché tibia (desarrollo día a día) el costo es chico. Medido y reproducible: ver sección 4 de [`BENCHMARKS.md` de ccdd-gate](https://github.com/MauricioPerera/ccdd-gate/blob/main/BENCHMARKS.md#4-costo-de-rust-vs-python-en-el-gate-reproducible).

### Export para el gate

Esta seccion describe el exportador historico usado con MCP. El adaptador nativo
crea su propio export temporal, conserva test_command y usa cwd de la raiz por
defecto; consultar [las diferencias del perfil](./native-level2.md).

El gate se corre sobre el **export** generado por `scripts/export_gate_contract.py` (normalización ASCII + `target`/`tests` reescritos relativos al export): `lint_task_contract` recibe el texto del export + tests, y `run_integration_gate` recibe la ruta del export en disco. Por defecto el export se escribe en la raíz del repo como `<task>.gate.md` (gitignorado vía `*.gate.md`) para que las rutas reescritas no contengan `..`, como exige el gate real (`tc-tests-frozen`).

## Precedencia del budget

En el perfil nativo la politica se identifica mediante commit aprobado y topes
explicitos; no se verifica una firma criptografica de umbrales. La mencion de
config firmada abajo describe la politica gobernada esperada, no una garantia
automatica de autenticacion del adaptador.

- **Con gate CCDD disponible (nivel 2):** la config firmada por el gate manda. El `budget` del frontmatter solo puede ser **<=** los topes firmados; ante cualquier conflicto gana la config firmada del gate.
- **Sin gate (solo nivel 1):** el `budget` del contrato es declarativo/informativo. El validador incluido solo verifica su **presencia** en el frontmatter; no aplica (enforce) los topes.

## Ciclo de vida del contrato

1. **draft** — contrato redactado en `knowledge/contracts/<task>.md`.
2. **validated** — validador de nivel 1 (y `lint_task_contract` si hay gate) en verde.
3. **implemented** — `test_command` del contrato en verde.
4. **verified** — la salida **REAL** de los comandos (validador + `test_command`, y gate si corre) se pega en `.agents/logs/<task>-REPORT.md`. Ese directorio está gitignorado a propósito: es evidencia local, no parte del repo. Opcionalmente, ese REPORT lleva un **envelope de atestación** (mismo dialecto mini-YAML que el frontmatter de contratos) al tope: identidad de quién corrió el gate (`agent`, `model`), el `command` + `exit_code`, y dos hashes recomputables (`output_sha256` del propio texto pegado abajo, `contract_sha256` del contrato al momento de verificar). `python scripts/validate_attestation.py .agents/logs .` lo verifica: reportes sin envelope dan WARNING (retrocompatible, no bloquea), un envelope incompleto o con algún hash que no calza da ERROR. NO es paso de CI (mismo motivo que `validate_perimeter.py`: la evidencia que audita es local y gitignorada). Ver [attestation-gate](./contracts/attestation-gate.md).

## Aprobacion de calidad del proyecto

La validacion estructural de la plantilla no sustituye la aprobacion de comportamiento. Para nuevos proyectos, integrar los gates aplicables, oraculos funcionales, adversariales y UI en el [protocolo de aprobacion integrada](quality-approval.md), con politica y referencia aprobada explicitas. El protocolo compone controles existentes y no altera el conteo anterior de 19 gates.


## Diagnostico reproducible de comandos

En Windows, `python scripts/validation_runtime.py suite`, `preflight` o
`contracts` prioriza Git para Windows si esta instalado en una ubicacion
estandar. Solo cambia el entorno del proceso y sus hijos. `preflight.py`,
`validate_test_commands.py` y `run_profile.py` tambien preparan ese entorno
al ejecutarse como CLI. Si no hay Git nativo, conservan el PATH existente;
no instalan programas ni alteran certificados o configuracion global.

Cada comando conserva su timeout individual de 180 segundos. El preflight
calcula para el gate agregado `max(300, numero_de_contratos * 180 + 30)`;
asi el limite global no interrumpe comandos validos por sumar sus duraciones.
Un comando colgado sigue fallando por su propio limite. El progreso imprime
RUN y el resultado con duracion antes de iniciar el siguiente comando.

Para conservar la medicion:

```text
python scripts/validation_runtime.py contracts --timings-json tiempos.json
```

El JSON incluye ruta, scope, duracion y estado PASS/FAIL/TIMEOUT por contrato,
sin stdout, stderr ni el texto del comando. No introduce cache ni omite pruebas.
La ausencia opcional de evidencia sigue siendo SKIP en el preflight. Ver
[el contrato del diagnostico](contracts/validation-diagnostics.md).

## Aceptacion y muestras ejecutables

El nuevo perfil [acceptance](acceptance.md) exige un SHA aprobado, inventario
completo y matriz por obligacion. El Nivel 1 historico sigue siendo validacion
estructural y de comandos: su verde no sustituye el punto de aceptacion.

`oracle_files` es opcional por compatibilidad historica, pero obligatorio en
acceptance. Si esta presente se validan rutas exactas, existencia e interseccion
con `touch_only`; baseline y gate confiable comparan cada archivo aprobado.
`test_runner` activa ejecucion instrumentada con casos positivos en cada archivo
seleccionado, en vez de usar unicamente exit code. Su ausencia conserva la
semantica historica y no permite acceptance.

```text
python scripts/validate_documentation_examples.py
```

Este check extrae las muestras del quickstart real y comprueba contrato valido,
stub rechazado e implementacion aprobada con dos casos. Se ejecuta tambien en CI.
Los requisitos de la suite completa son los declarados en el quickstart; los
validadores estructurales individuales mantienen sus dependencias documentadas.

El plazo por contrato es 180s por defecto. `test_timeout` declara un entero
entre 1 y 3600 segundos aprobado con el contrato; `--timeout` cambia el valor
por defecto de los contratos que no lo declaran. El contrato init-project
usa 300s porque verifica la suite en una copia inicializada. El modo
preflight --contract usa 120s historicos salvo plazo declarado y respeta
test_runner; no degrada un oraculo instrumentado a exit code libre.
