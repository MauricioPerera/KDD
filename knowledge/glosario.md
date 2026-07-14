---
type: 'Concept'
title: 'Glosario'
description: 'Indice unico de los terminos propios de KDD (OKF+CCDD). Cada entrada enlaza al nodo que la define en detalle; este nodo no duplica la definicion normativa, solo la resume y apunta.'
tags: ['ccdd', 'okf', 'glosario', 'reference']
---

# Glosario

Indice unico de vocabulario. Gap de onboarding real (auditoria DX de este
repo): ~15 terminos propios estaban dispersos en 5+ nodos sin un solo
lugar para buscarlos. Cada entrada es un resumen de 1-2 lineas + link al
nodo normativo — la definicion completa vive alla, no aca (OKF §4: no
duplicar contenido).

## OKF (formato de conocimiento)

- **OKF (Open Knowledge Format)** — formato minimalista para estructurar
  conocimiento como markdown + frontmatter YAML indexable. Ver
  [OKF-SPEC](./OKF-SPEC.md).
- **Nodo OKF** — un archivo `.md` con frontmatter valido (`type`, `title`,
  `description`, `tags`), enlazado desde `knowledge/index.md`.
- **KU (Knowledge Unit)** — la unidad minima de conocimiento que representa
  un nodo OKF (un concepto, un contrato, un modelo de datos).

## CCDD (contratos de tarea)

- **CCDD (Contract-Driven Development)** — metodologia para gobernar
  desarrollo con agentes efimeros via contratos estrictos y umbrales
  deterministas. Ver [validacion.md](./validacion.md).
- **Task contract** — un `.md` en `knowledge/contracts/` con frontmatter
  hibrido OKF+CCDD (`task`, `intent`, `target`, `signature`,
  `test_command`, `budget`, `tests`, `tests_sha256`, `touch_only`,
  `deps_allowed`, `forbids`) que define UNA funcion a implementar.
  Plantilla lista para copiar:
  [TEMPLATE-task-contract.md](./contracts/TEMPLATE-task-contract.md).
- **Intent** — la UNA frase con UN verbo que resume que hace la tarea. Un
  "y ademas..." rompe la regla `tc-intent-atomic`.
- **Oraculo congelado** (frozen oracle) — el archivo de tests de un
  contrato, escrito ANTES de delegar la implementacion. Es la fuente de
  verdad de "esto esta bien"; quien lo escribe nunca es quien implementa.
- **Sello** (`tests_sha256`) — hash SHA256 (newlines normalizados a LF)
  del archivo de tests, congelado en el frontmatter. Si el oraculo cambia
  sin re-sellar el hash, el gate lo detecta como ERROR — el diff del sello
  hace visible el cambio en review. Generarlo:
  `python scripts/validate_contracts.py --hash <ruta/tests>`.
- **`touch_only`** — perimetro de la delegacion como DATO: lista de
  rutas/patrones `fnmatch` que el implementador puede tocar.
  `scripts/validate_perimeter.py` lo verifica contra el diff real
  (`OUT_OF_PERIMETER` / `TESTS_TOUCHED` si se viola).
- **`budget`** — topes declarativos de complejidad
  (`max_cyclomatic_complexity`, `max_nesting_depth`). En Nivel 1 son
  informativos (el validador solo checkea que esten presentes); se
  ENFORCEAN de verdad solo con el gate MCP de Nivel 2. Ver precedencia en
  [validacion.md](./validacion.md).
- **`deps_allowed`** — dependencias externas permitidas para el target
  (vacio = solo stdlib del lenguaje).
- **`forbids`** — capacidades explicitamente prohibidas para el
  implementador (`network`, `subprocess`, `llm`). Convencion de los gates
  de Nivel 1 de este repo; la unica excepcion documentada es
  [test-command-gate](./contracts/test-command-gate.md) (su intent ES
  correr un comando).

## Gates y niveles

- **Gate** — script determinista (`scripts/validate_*.py` o
  `scripts/scan_*.py`) que verifica una propiedad mecanica. Sin LLM salvo
  la excepcion documentada por contrato.
- **Nivel 1** — gates obligatorios, corren local y en CI, Python puro sin
  red/subprocess/LLM (salvo la excepcion de `test-command-gate`). Lista
  completa: [validacion.md](./validacion.md#nivel-1--incluido-y-obligatorio-local--ci).
- **Nivel 2** — gate opcional via MCP `ccdd-complexity`: enforcea el
  `budget` de verdad (complejidad ciclomatica real) y otros checks que
  requieren mas que regex/AST simple.
- **Perimeter gate** — `scripts/validate_perimeter.py`, corrido por el PM
  en verificacion (no en CI): compara el diff real contra `touch_only`.
- **Export del gate** (`<task>.gate.md`) — `scripts/export_gate_contract.py`
  produce un contrato exportado consumible por el gate MCP de Nivel 2.

## Ciclo de vida y proceso

- **Ciclo `draft -> validated -> implemented -> verified`** — estados por
  los que pasa un contrato. Ver
  [validacion.md](./validacion.md#nivel-1--incluido-y-obligatorio-local--ci).
- **RECON** — verificar cada suposicion del contrato contra el estado
  real del repo ANTES de delegar (comando real, no lectura). Ver
  [metodologia-ejecucion.md](./metodologia-ejecucion.md).
- **Red-team (de la definicion de hecho)** — antes de delegar, buscar si
  algun camino cumple los comandos del contrato sin cumplir la intencion
  real (test que pasa en vacio, oraculo reescribible, budget evadible).
- **Verificar por artefacto** — la palabra del agente no cuenta: solo
  salidas reales de comandos (exit codes, output de tests) validan una
  tarea. Principio central de
  [metodologia-ejecucion.md](./metodologia-ejecucion.md).

## Ver tambien

- [OKF-SPEC.md](./OKF-SPEC.md) — spec normativa completa de nodos OKF.
- [validacion.md](./validacion.md) — referencia normativa de gates y
  ciclo de vida.
- [quickstart.md](./quickstart.md) — estos terminos en accion, paso a
  paso.
- [por-que-kdd.md](./por-que-kdd.md) — posicionamiento frente a otras
  metodologias.
