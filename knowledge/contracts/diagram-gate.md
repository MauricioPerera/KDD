---
type: 'Task Contract'
title: 'Gate de diagramas Mermaid (flowchart/gantt/pie/journey, Python puro)'
description: 'Validador determinista de diagramas Mermaid (flowchart, gantt, pie, journey) contra un contrato JSON declarativo por tipo. Parsers propios en Python puro, sin subprocess/red/LLM: NO usa el parser real de mermaid (eso exigiria Node.js via subprocess, prohibido por forbids en los gates de este repo). Cobertura deliberadamente parcial: solo estos 4 tipos. Ver el proyecto hermano mermaid-gate (Node, parser real, 20 tipos de diagrama) para verificacion con fidelidad completa fuera de la restriccion de dependencias de este repo.'
tags: ['ccdd', 'diagramas', 'mermaid', 'gate', 'infra']

task: diagram-gate
intent: "Validar la estructura de un diagrama Mermaid (flowchart, gantt, pie o journey) contra un contrato JSON por tipo, sin depender de Node.js ni del parser real de mermaid."
target: scripts/validate_diagrams.py
signature: "def validate_diagram(mmd_path, contract_path) -> list"
test_command: "python -m unittest tests/test_validate_diagrams.py"
budget:
  max_cyclomatic_complexity: 14
  max_nesting_depth: 4
tests: "tests/test_validate_diagrams.py"
tests_sha256: "e0ef690cc83b80f9192b6d500c86962d3d88ebf138bbf1a4d696bb7abdeb90a9"
touch_only: ['scripts/validate_diagrams.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de diagramas Mermaid (validate_diagrams)

## Intent
Verificar de forma determinista que un diagrama Mermaid (`flowchart`,
`gantt`, `pie` o `journey`) contiene la estructura que un contrato JSON
declara obligatoria, sin ejecutar el parser real de mermaid (Node.js,
requeriria `subprocess`, prohibido por `forbids` en los gates de este
repo). Es la contraparte pure-Python, de cobertura parcial (4 de los 20
tipos de mermaid-gate), del proyecto hermano `mermaid-gate` (Node, parser
real). Convencion del contrato JSON: `knowledge/diagram-contract-spec.md`.
Nota de proceso: este contrato se implemento directo en una sesion (no via
el pipeline PM/dev delegado descrito en `knowledge/metodologia-ejecucion.md`),
por eso no lleva numeracion `CONTRACT-NN` ni reporte en `docs/reports/`.

## Interface
- `parse_flowchart(text) -> {'nodes': [{'id','label'}], 'edges': [{'from','to','label'}]}`
  — nodo con shape `[ ]`/`{ }`/`( )`, edges `-->`, `-->|label|`, `---`, `-.->`.
  Nodo sin shape usa su id como label.
- `parse_gantt(text) -> {'tasks': [{'id','label','section','start','end'}], 'sections': [...]}`
  — task `<label> :<id>, <start|after id>, <Nd>`. `start`/`end` (YYYY-MM-DD)
  se derivan solo si hay fecha literal + duracion `Nd`, o `after <id>` con
  `<id>` ya visto ANTES en el texto (pasada unica, no resuelve forward refs).
- `parse_pie(text) -> {'slices': [{'label','value'}]}` — linea `"label" : valor`.
- `parse_journey(text) -> {'tasks': [{'section','task','score','people'}], 'sections': [...], 'actors': [...]}`
  — linea `task: score: persona1, persona2`.
- `get_diagram_type(text) -> str|None` — primer token no vacio/no-comentario
  del texto (`'flowchart'`, `'graph'`, `'gantt'`, `'pie'`, `'journey'`, o
  cualquier otro tipo de mermaid no soportado).
- `validate_diagram(mmd_path, contract_path) -> list` — findings
  `{'file','level','rule','msg'}` ordenados por (rule, msg). Reglas, niveles
  y mensajes EXACTOS por tipo: docstring del oraculo congelado
  `tests/test_validate_diagrams.py`.
- `main(argv) -> int` — uno o mas paths (archivo `.mmd` o directorio; default
  `['examples/diagrams']`); escanea `*.mmd` recursivo; cada `.mmd` espera un
  `<mismo-nombre>.diagram-contract.json` al lado (capa opcional: sin
  contrato, WARNING `CONTRACT_MISSING`, no bloquea); path ausente o sin
  `.mmd` -> INFO `PATH_MISSING`, no bloquea; exit 1 solo si hay >=1 ERROR;
  Resumen honesto con diagramas EFECTIVAMENTE verificados (pares con
  contrato presente).

## Invariants
- Python stdlib puro (`json`, `re`, `os`, `datetime`); sin red, sin
  subprocess, sin navegador; determinista; mensajes ASCII.
- Solo soporta `diagram_type` en `{flowchart, gantt, pie, journey}` (`graph`
  es alias de `flowchart` en el `.mmd`). Un contrato que pida otro tipo, o
  un `.mmd` de otro tipo sin `diagram_type` explicito en el contrato,
  produce `DIAGRAM_TYPE_UNSUPPORTED` (ERROR) en vez de intentar parsearlo
  de forma incorrecta.
- El contrato JSON es un subconjunto deliberadamente simple del formato YAML
  de `mermaid-gate` (mismo vocabulario por tipo: `min_nodes`/`max_nodes`/
  `required_nodes`/`required_edges` para flowchart; `min_tasks`/`max_tasks`/
  `required_sections`/`required_tasks` para gantt y journey (mismos nombres,
  distinto shape de `required_tasks`); `min_slices`/`max_slices`/
  `required_slices` para pie; `required_actors` solo en journey) pero en
  JSON, no YAML — este repo no tiene parser YAML de proposito general
  (mismo precedente que `rule_engine.py`, JSON para `examples/rules/*.rules.json`).
- Cada parser NO maneja el 100% de la gramatica real de su tipo (flowchart:
  sin subgraphs/estilos/edges multi-linea; gantt: sin tags de estado
  active/done/crit antes del id, sin resolver `after` hacia adelante; pie:
  solo lineas `"label" : valor`; journey: una persona/task por linea) —
  cobertura parcial declarada, no un bug oculto.

## Examples
- `flowchart TD\n    A[Inicio] --> B{Condicion}\n` con contrato
  `{"required_nodes":[{"id":"A","label":"Inicio"}]}` -> `[]`.
- Gantt con `Wireframes :a1, 2026-01-01, 5d` seguido de
  `Mockups :a2, after a1, 3d`, contrato con
  `required_tasks: [{"id":"a2","start":"2026-01-06"}]` -> `[]` (start de a2
  se deriva del end de a1).
- Pie `"A" : 40` con contrato `required_slices: [{"label":"A","value":41}]`
  -> `SLICE_VALUE_MISMATCH` (ERROR), exit 1.
- Journey task `Confirmar pago: 4: Cliente, Sistema` con contrato
  `required_tasks: [{"task":"Confirmar pago","people":["Auditor"]}]` ->
  `TASK_MISSING_PERSON` (ERROR): `people` es subset, no exige match exacto
  de la lista completa, pero SI exige que cada persona listada este
  presente.

## Do / Don't
- DO: estilo de `validate_ux_page.py`/`validate_skills.py` (findings,
  Resumen honesto, capa opcional).
- DO: un `_validate_<tipo>` + un `parse_<tipo>` separados por tipo, unidos
  por el dict `_VALIDATORS` en `validate_diagram` — mismo patron que
  `EXTRACTORS` en el gate.js de `mermaid-gate` (agregar un tipo nuevo es
  sumar una entrada, no tocar el dispatch).
- DON'T: tocar `tests/test_validate_diagrams.py` (oraculo congelado,
  sellado).
- DON'T: usar `subprocess` para invocar Node/mermaid real — eso es
  exactamente lo que este gate evita, por `forbids` de este repo.
- DON'T: fingir soporte para tipos de diagrama fuera de
  `{flowchart, gantt, pie, journey}`; deben fallar explicito
  (`DIAGRAM_TYPE_UNSUPPORTED`), no intentar parsearse con la gramatica
  equivocada.

## Tests
`python -m unittest tests/test_validate_diagrams.py` verde SIN modificar el
oraculo; suite completa sin regresiones.

## Constraints
- Tocar SOLO: `scripts/validate_diagrams.py`. Reporte local en
  `.agents/logs/C32-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: el oraculo exigiera comportamiento contradictorio; el
  budget de complejidad no alcanzara sin romper un test; o soportar un caso
  de sintaxis flowchart exigiera un parser real (no regex) — en ese caso el
  limite se documenta, no se fuerza con una heuristica fragil.
