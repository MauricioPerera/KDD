---
type: 'Task Contract'
title: 'Capa de despacho del MCP server de gates KDD'
description: 'Logica pura (stdlib, sin el SDK mcp) que sabe que script scripts/*.py correr por cada gate y como armar su argv. El wiring MCP real (scripts/mcp_server.py, fuera de este contrato) importa este modulo. Separado a proposito para que la logica de despacho sea testeable sin el SDK mcp instalado.'
tags: ['ccdd', 'gate', 'infra', 'mcp']

task: mcp-gate-dispatch
intent: "Mapear cada gate de KDD a su script y argv, y ejecutarlo via subprocess, sin depender del SDK mcp."
target: scripts/mcp_gate_dispatch.py
signature: "def run_gate(tool_name, params, repo_root='.', timeout=120) -> dict"
test_command: "python -m unittest tests/test_mcp_gate_dispatch.py"
budget:
  max_cyclomatic_complexity: 14
  max_nesting_depth: 4
tests: "tests/test_mcp_gate_dispatch.py"
tests_sha256: "a5a3fd5f39f16074e884f563283a4d2981e11cfc6317e2a58d4d18f4689ca945"
touch_only: ['scripts/mcp_gate_dispatch.py']
deps_allowed: []
forbids: ['network', 'llm']
---

# Contract: Capa de despacho del MCP server (mcp_gate_dispatch)

## Intent
Primer paso de exponer los gates de KDD como tools MCP (gap identificado
en la auditoria delta: "MCP server propio... expone los gates como tools
MCP"). Este contrato cubre SOLO la logica de despacho — que script correr,
como armar su `argv`, como ejecutarlo — deliberadamente separada del
wiring MCP real (`scripts/mcp_server.py`, que usa el SDK `mcp` via
`FastMCP` y NO esta gobernado por este contrato, ya que ese SDK es una
dependencia externa que rompe la convencion `deps_allowed: []` de todos
los demas contratos de este repo). Esta capa reusa `scripts/*.py` TAL
CUAL via `subprocess.run` — cero reimplementacion, cero drift entre el
CLI y la tool MCP.

## Por que este gate rompe la convencion forbids: subprocess (otra vez)
Igual que [test-command-gate](./test-command-gate.md), el intent de este
modulo ES ejecutar los scripts de gate como subprocess — no hay forma de
reusar `scripts/*.py` sin invocarlos como proceso. `forbids` es
`['network', 'llm']` unicamente, mismo patron que `test-command-gate`.

## Interface
- `GATE_SPECS` — dict `{tool_name: {'script','params','defaults'}}` para
  los 12 gates: `validate_contracts`, `validate_specs`, `validate_okf`,
  `lint_ascii`, `validate_rules`, `validate_skills`, `validate_changelog`,
  `validate_ux_page`, `validate_diagrams`, `validate_test_commands`,
  `scan_secrets`, `validate_attestation`.
- `build_argv(tool_name, params) -> list[str]` — arma
  `[sys.executable, '<repo>/scripts/<gate>.py', ...args]`. Un valor
  `list` en `params` se expande a multiples argv (nunca se unen con
  espacios: `subprocess.run` recibe una lista, no pasa por shell — evita
  toda la clase de bugs de `shlex`/comillas que tuvieron otros gates de
  este repo). `KeyError` si `tool_name` no existe.
- `run_gate(tool_name, params, repo_root='.', timeout=120) ->
  {'exit_code','stdout','stderr'}` — corre `build_argv(...)` con
  `subprocess.run(cwd=repo_root, capture_output=True, text=True,
  timeout=timeout)`. Timeout se traduce a
  `{'exit_code': None, 'stdout': '', 'stderr': 'timeout after Ns'}`, sin
  propagar la excepcion.
- `run_all_level1(repo_root='.') -> {'overall_ok': bool, 'results':
  {tool_name: {...}}}` — corre los 11 gates de Nivel 1 (todo
  `GATE_SPECS` EXCEPTO `validate_attestation`, que es local-only, ver
  [attestation-gate](./attestation-gate.md)) con sus defaults.
- `seal_tests(tests_path, repo_root='.') -> {'hash': str|None,
  'exit_code': int, 'stdout': str}` — corre
  `validate_contracts.py --hash <tests_path>` y extrae el hash del
  stdout. `hash` es `None` si el exit code no fue 0.

## Invariants
- `run_gate` nunca lanza excepcion (ni por exit code !=0, ni por
  timeout).
- `run_all_level1` NUNCA incluye `validate_attestation` en `results`.
- `build_argv` nunca une un parametro `list` con espacios en un solo
  string argv — siempre elementos separados de la lista.

## Examples
- `build_argv('validate_contracts', {})` -> `[sys.executable,
  '.../scripts/validate_contracts.py', 'knowledge/contracts']`.
- `build_argv('scan_secrets', {'dirs': ['a', 'b']})` -> termina en
  `['a', 'b']` (dos argv separados).
- `run_all_level1(repo_root='.')` sobre un repo con contratos rotos/faltantes
  -> `overall_ok: False`, 11 entradas en `results` (ver nota de RECON abajo
  sobre por que el oraculo NUNCA corre esto contra el repo real).
- `seal_tests('tests/test_x.py', repo_root='.')` -> `{'hash': '<64
  hex>', 'exit_code': 0, ...}`.

## Do / Don't
- DO: reusar `scripts/*.py` via subprocess, nunca reimplementar su
  logica.
- DO: pasar `argv` como lista a `subprocess.run` (nunca construir un
  string y pasar por shell).
- DON'T: importar el SDK `mcp` en este modulo (esa es responsabilidad de
  `scripts/mcp_server.py`, fuera de este contrato).
- DON'T: agregar `validate_attestation` a `run_all_level1` (es
  local-only, no Nivel 1 de CI).

## Tests
(Los tests estan en `tests/test_mcp_gate_dispatch.py`, oraculo congelado.
`TestRunGate` y `TestSealTests` corren gates individuales livianos CONTRA
EL REPO REAL de KDD, para verificar la integracion real con
`scripts/*.py`. `TestRunAllLevel1` en cambio SIEMPRE usa un `tmpdir`
aislado, NUNCA el repo real — ver la nota siguiente.)

### Por que `run_all_level1` NUNCA se prueba contra el repo real (ni en el oraculo, ni a mano)
`run_all_level1` incluye `validate_test_commands`, que corre el
`test_command` de CADA contrato — incluido `init-project.md`, cuyo test
(`test_gates_verdes_post_apply_en_copia`) copia el repo entero y vuelve a
correr `python -m unittest discover` DENTRO de esa copia. Esa corrida
anidada incluye `tests/test_mcp_gate_dispatch.py` — si ese archivo
llamara a `run_all_level1(repo_root=REPO_ROOT)`, cada nivel de copia
volveria a disparar el mismo ciclo completo: explosion recursiva
verificada empiricamente (una corrida real tardo mas de 3 minutos y no
termino en ese tiempo). Este NO es un bug de `mcp_gate_dispatch.py`
mismo — es una interaccion real entre `validate_test_commands` (Nivel 1,
ya en produccion) y el test de auto-copia de `init-project.md` (tambien
ya en produccion) que solo se activa si algo llama `run_all_level1`
contra el repo real desde DENTRO de la suite de tests del repo. Por eso:
NUNCA agregues un test que llame `run_all_level1(repo_root=REPO_ROOT)` (o
equivalente) a este archivo, y no lo corras a mano contra el repo real
tampoco (esperalo colgado varios minutos, no es un error tuyo).

## Constraints
- Sin red, sin LLM (`forbids`). `subprocess` permitido (intent del
  modulo).
- Solo stdlib (`deps_allowed: []`): `subprocess`, `sys`, `os`, `re`.
- `touch_only`: unicamente `scripts/mcp_gate_dispatch.py`.
- PARAR y reportar si necesitas conectarte a la red.

## Criterios de aceptacion
- [ ] `python -m unittest tests/test_mcp_gate_dispatch.py` sale en 0 (debe
      terminar en segundos, no minutos — si tarda mas de ~30s algo se
      esta corriendo contra el repo real que no deberia).
- [ ] `python -c "import mcp_gate_dispatch as gd; print(gd.run_gate('validate_contracts', {}, '.'))"`
      corrido desde `scripts/` contra el repo real imprime `exit_code: 0`.
