---
type: 'Task Contract'
title: 'Auditor de seals debiles: el sello garantiza integridad, no fuerza'
description: 'Herramienta ADVISORY que detecta oraculos congelados que el sello certifica como integros pero que no pueden fallar: sin asserts reales (assert True no cuenta), sin funciones de test, o sin referenciar jamas al target. Cierra la mitad diferida del feedback externo del Contrato 32 ("help catch weak test seals early"). Advisory por diseno: warnings y exit 0; --strict para equipos que quieran imponerlo. NO es gate de CI ni entra en GATE_SPECS.'
tags: ['ccdd', 'gate', 'infra', 'dx']

task: seal-audit
intent: "Reportar contratos cuyo oraculo sellado no puede fallar, como advertencia temprana de seal debil."
target: scripts/audit_seals.py
signature: "def audit_seals(contracts_dir='knowledge/contracts', repo_root='.') -> dict"
test_command: "python -m unittest tests/test_audit_seals.py"
budget:
  max_cyclomatic_complexity: 14
  max_nesting_depth: 4
tests: "tests/test_audit_seals.py"
tests_sha256: "d9594ece469f20c181a3594ac8bdc5ee8d69f0c73d2e7454fb889531dbb86351"
touch_only: ['scripts/audit_seals.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Auditor de seals debiles (seal-audit)

## Intent
Mitad diferida del feedback externo que origino el Contrato 32: "help
catch weak test seals early". El sello (`tests_sha256`) garantiza que el
oraculo no cambio -- NO garantiza que el oraculo tenga fuerza. Un archivo
de tests vacio, sin asserts reales o que jamas menciona al target pasa
`validate_contracts` verde y sella exactamente nada. Este auditor detecta
esa AUSENCIA mecanica. La calidad semantica de los asserts (que un assert
no-trivial pruebe algo util) queda deliberadamente fuera: eso es trabajo
de mutation testing (`mutation_audit` del MCP ccdd-complexity), no de
heuristicas estaticas.

Advisory por diseno: la frontera mecanica/juicio de este repo. Detectar
la ausencia es mecanico; decidir que es inaceptable es del equipo
(`--strict` opt-in).

## Interface
- Reglas (constantes str del modulo): `WEAK_TESTS_MISSING`,
  `WEAK_TESTS_EMPTY`, `WEAK_TESTS_UNPARSEABLE`,
  `WEAK_NO_TEST_FUNCTIONS`, `WEAK_NO_ASSERTS`,
  `WEAK_TARGET_UNREFERENCED`.
- `audit_contract(contract_path, repo_root) -> list[dict]`: findings
  `{'contract': basename, 'rule': str, 'msg': str}` de UN contrato;
  lista vacia = sano. Frontmatter via `validate_contracts.parse_frontmatter`
  (CRLF-safe); un contrato sin frontmatter o sin claves `tests`/`target`
  no es auditable y devuelve [] (la estructura la valida
  `validate_contracts`, no este auditor).
- `audit_seals(contracts_dir='knowledge/contracts', repo_root='.') ->
  {'findings': [...], 'checked': int}`: recorre `*.md` (salta
  `TEMPLATE-*`), findings ordenados por (contract, rule); `checked`
  cuenta solo contratos auditables.
- `main(argv) -> int`: argv estilo `sys.argv`; posicional opcional
  contracts_dir, flags `--repo-root DIR` y `--strict`. Imprime una linea
  por finding (incluye la regla) + resumen. Sin `--strict` SIEMPRE 0
  (advisory); con `--strict`, 1 si hay findings, 0 limpio.

## Invariants
- Semantica congelada por el oraculo:
  - `assert` con test constante (`assert True`) NO cuenta como assert
    real; `self.assert*`/`assertRaises` (cualquier atributo que empiece
    con `assert`) SI cuentan. Deteccion via `ast` (stdlib), nunca regex
    sobre el codigo.
  - Funcion de test = `FunctionDef`/`AsyncFunctionDef` cuyo nombre
    empieza con `test` (incluye metodos de clases unittest).
  - Referencia al target = el stem del target (basename sin extension)
    aparece como substring del source de tests (cubre imports Y
    invocaciones por ruta).
  - `target == tests` (contratos de coherencia auto-referenciales, como
    agents-context-rule o versioning-plantilla): TARGET_UNREFERENCED se
    omite -- un archivo se cubre a si mismo trivialmente.
  - Tests no-Python (p.ej. `.js` de example-node-greet): solo
    MISSING/EMPTY/TARGET_UNREFERENCED; el analisis AST es Python-only.
  - MISSING/EMPTY/UNPARSEABLE cortocircuitan el resto de reglas del
    contrato.
- Cero dependencias externas (stdlib: `ast`, `os`, `sys`) + el helper
  `parse_frontmatter` del modulo hermano. Sin subprocess, sin red, sin
  LLM (`forbids` completo -- mas estricto que preflight: este auditor
  solo LEE archivos).
- Nunca lanza por un contrato problematico: el problema es un finding o
  un salto, jamas un traceback.
- ASCII puro (lo audita `lint_ascii`).

## Examples
- `python scripts/audit_seals.py` -> sobre este repo: 0 findings, 31
  auditados, exit 0.
- Un contrato cuyo oraculo es `def test_x(): assert True` ->
  `WEAK_NO_ASSERTS` (WARNING), exit 0; con `--strict`, exit 1.
- `python scripts/audit_seals.py knowledge/contracts --strict` en el CI
  de un proyecto instanciado que ELIJA imponerlo.

## Do / Don't
- DO mantenerlo advisory por default: el exit code sin `--strict` es 0
  aunque haya findings.
- DO saltar en silencio lo que `validate_contracts` ya vigila
  (estructura del frontmatter): un auditor no duplica al gate.
- DON'T agregarlo a `GATE_SPECS` de `mcp_gate_dispatch`: eso lo meteria
  en `LEVEL1_GATES` y romperia el oraculo congelado del preflight (12
  gates exactos). Si algun dia se promueve a gate, ese cambio es su
  propio contrato con re-sellado explicito de ambos oraculos.
- DON'T cablearlo en `.github/workflows/validate.yml` ni en el `GATES`
  de `benchmark_gates.py`.
- DON'T intentar juzgar la CALIDAD de un assert no-trivial: eso es
  mutation testing, fuera de este contrato.

## Tests
Oraculo congelado en `tests/test_audit_seals.py` (sellado en
`tests_sha256`): 15 tests sobre fixtures tmpdir (nunca el repo vivo) --
sanos (py, auto-referencial, no-python), las 6 debilidades, recorrido de
dir con salto de TEMPLATE y orden, contrato sin frontmatter sin crash, y
exit codes de `main` (advisory 0 con findings, `--strict` 1/0).
`python -m unittest tests/test_audit_seals.py`.

## Constraints
- `touch_only: scripts/audit_seals.py` -- oraculo, contrato y docs los
  gobierna el orquestador (Contrato de ejecucion 33).
- Budget: complejidad ciclomatica <= 14, anidamiento <= 4.
- `test_command` < 120s (lo ejecuta `validate_test_commands` en CI).
- PARAR y reportar si: algun test del oraculo resulta incumplible sin
  violar otra clausula (p.ej. el corte por budget), o si cumplirlo exige
  tocar archivos fuera de `touch_only`. Documentar con evidencia;
  prohibido editar el oraculo o inventar tests.
