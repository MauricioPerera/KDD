---
type: 'Task Contract'
title: 'Preflight: dry-run local de los 19 gates'
description: 'CLI de diagnostico que corre los 19 gates de KDD (los 18 de Nivel 1 + validate_attestation, el local-only que CI nunca ve) contra el repo actual y reporta cuales fallarian ANTES de que un agente toque el codigo. Modo --contract: 3 chequeos acotados a un solo task contract (frontmatter, seal del oraculo, test_command). Nace de feedback externo real de adopcion. Misma familia que benchmark_gates.py: herramienta de mantenimiento, NO gate de CI.'
tags: ['ccdd', 'gate', 'infra', 'dx']

task: preflight
intent: "Reportar que gates de KDD fallarian sobre el repo actual, en una sola corrida local, antes de delegar trabajo a un agente."
target: scripts/preflight.py
signature: "def run_preflight(repo_root='.', contract=None, runner=None) -> dict"
test_command: "python -m unittest tests/test_preflight.py"
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: "tests/test_preflight.py"
tests_sha256: "709073598499749c809705a7b5e3d9b73ed8f423290b07bf3c2f76f176494c51"
touch_only: ['scripts/preflight.py']
deps_allowed: []
forbids: ['network', 'llm']
---

# Contract: Preflight (dry-run de los 19 gates)

## Intent
Feedback externo textual: "a built-in dry-run mode that shows which of the
12 gates would fail on the current contract before any agent touches the
code". El motor ya existe (`mcp_gate_dispatch.run_all_level1`, Contrato
mcp-gate-dispatch) pero SOLO es invocable via el MCP server (`pip install
mcp` + cliente MCP): para onboarding eso es una barrera. Este contrato le
pone una boca CLI de cero dependencias, y agrega el unico lugar donde los
19 gates pueden correr juntos (CI corre 18; `validate_attestation` es
local-only porque `.agents/logs/` esta gitignoreado).

NO es un gate nuevo de Nivel 1: es diagnostico opt-in, mismo estatus que
`benchmark_gates.py`. No se cablea en CI por si mismo (CI ya corre cada
gate de Nivel 1 como paso propio); el conteo de `ALL_GATES` sigue
`mcp_gate_dispatch.LEVEL1_GATES` + `validate_attestation` sin
duplicarlo -- ver `knowledge/validacion.md` para el conteo vigente de
gates de Nivel 1.

## Interface
- `ALL_GATES`: lista = `mcp_gate_dispatch.LEVEL1_GATES` +
  `['validate_attestation']` (19 nombres, en ese orden). Derivada del
  dispatch, nunca hardcodeada aparte.
- `run_gate`: referencia de modulo inicializada a
  `mcp_gate_dispatch.run_gate` (indireccion deliberada: el oraculo la
  parchea; `run_preflight` con `runner=None` la resuelve EN CADA llamada,
  no la captura en el default).
- `run_preflight(repo_root='.', contract=None, runner=None) -> dict`:
  - Modo full (`contract is None`): corre los 19 gates de `ALL_GATES` en
    orden via `runner(name, {}, repo_root=repo_root)`. Devuelve
    `{'mode': 'full', 'overall_ok': bool, 'results': {gate: dict},
    'lines': [str]}` donde cada dict de gate es el retorno de `run_gate`
    (`{'exit_code','stdout','stderr'}`; timeout => `exit_code None`).
  - Modo contract (`contract='<task>'`): NO corre los 19 gates. Corre 3
    chequeos, en este orden y con estas claves en `results`:
    1. `frontmatter` -- `knowledge/contracts/<task>.md` existe bajo
       `repo_root` y su frontmatter declara `tests`, `tests_sha256` y
       `test_command` (parseo CRLF-safe, valores con o sin comillas).
    2. `seal` -- sha256 del archivo `tests` (contenido normalizado a LF,
       utf-8) igual a `tests_sha256` (bit-compatible con
       `validate_contracts.py --hash`).
    3. `test_command` -- ejecuta el comando (split con `shlex`,
       `posix=False` en Windows como validate_test_commands, cwd =
       `repo_root`, timeout 120s) y propaga su exit code real.
    Cada chequeo devuelve la misma shape `{'exit_code','stdout','stderr'}`
    (0 = PASS). Un chequeo previo fallido marca los siguientes como
    fallidos (exit_code != 0, stderr explica que se salteo), nunca los
    ejecuta.
- `main(argv) -> int`: argv estilo `sys.argv`. Flags: `--repo-root DIR`
  (default `.`), `--contract NAME` (default None). Imprime `lines` a
  stdout y devuelve 0 si `overall_ok`, 1 si no.
- `lines`: una linea por gate/chequeo conteniendo el nombre y su estado
  `PASS` / `FAIL` / `TIMEOUT` (`TIMEOUT` = `exit_code None`), mas una
  linea resumen con `<pasados>/<total>` (`19/19`, `18/19`, `3/3`, ...).

## Invariants
- Cero dependencias externas: stdlib + modulos hermanos de `scripts/`
  (`mcp_gate_dispatch`; `validate_test_commands`/`validate_contracts` si
  el dev decide reutilizar sus helpers). Sin SDK `mcp`.
- `run_preflight` NUNCA lanza por un gate/chequeo fallido: los fallos son
  informacion (`exit_code` != 0), el unico canal de veredicto es
  `overall_ok` / el exit code de `main`.
- El modo contract jamas invoca `runner` (congelado por el oraculo).
- ASCII puro (este archivo lo audita `lint_ascii`).
- `subprocess` esta permitido SOLO como herencia del despacho
  (`mcp_gate_dispatch` ya lo usa bajo su propia excepcion documentada) y
  para el chequeo `test_command` -- mismo motivo que test-command-gate:
  ejecutar el comando declarado y leer su exit code ES el proposito.
  `forbids` mantiene `network` y `llm`.

## Examples
- `python scripts/preflight.py` -> tabla de 19 lineas + resumen `19/19`,
  exit 0 (repo verde).
- `python scripts/preflight.py --contract preflight` -> 3 lineas
  (`frontmatter`, `seal`, `test_command`) + resumen `3/3`.
- Un gate que excede 120s aparece como `TIMEOUT` y el resumen baja a
  `18/19`, exit 1.

## Do / Don't
- DO derivar los 19 nombres del dispatch (`LEVEL1_GATES` +
  `validate_attestation`); un gate nuevo en `GATE_SPECS` debe aparecer
  solo con actualizar el dispatch.
- DO reportar TODOS los gates aunque el primero falle (es un dry-run de
  diagnostico, no un short-circuit).
- DON'T llamar `run_all_level1` desde los tests contra el repo vivo
  (recursion documentada en `knowledge/mcp-server.md`); el oraculo usa
  runner fake + fixtures tmpdir y este contrato lo hereda como regla.
- DON'T cablear este script en `.github/workflows/validate.yml` ni
  sumarlo a `benchmark_gates.py` (su contrato congela la lista de gates
  que mide; este script no es un gate).
- DON'T duplicar la logica de despacho (script/argv por gate): eso vive
  en `mcp_gate_dispatch` y tiene su propio contrato.

## Tests
Oraculo congelado en `tests/test_preflight.py` (sellado en
`tests_sha256`): 17 tests (14 + 3 de robustez post-AUDIT-05) -- constante `ALL_GATES`, modo full (orden,
params, repo_root, PASS/FAIL/TIMEOUT, resumen `N/19`, exit codes de
`main` con `run_gate` parcheado), modo contract (fixtures tmpdir: sano
LF, sano CRLF, seal desincronizado, exit code propagado del
test_command, contrato inexistente, prohibicion de correr gates, `main`
con flags). `python -m unittest tests/test_preflight.py`.

## Constraints
- `touch_only: scripts/preflight.py` -- el oraculo, este contrato y los
  docs los gobierna el orquestador (Contrato de ejecucion 32).
- Budget: complejidad ciclomatica <= 14, anidamiento <= 4 (mismo budget
  que mcp-gate-dispatch).
- `test_command` debe terminar en < 120s (lo ejecuta
  `validate_test_commands` en CI): por eso el oraculo no corre gates
  reales.
- PARAR y reportar si: algun test del oraculo congelado resulta
  incumplible sin violar otra clausula de este contrato (p.ej. la
  indireccion de `run_gate` choca con el budget), o si cumplirlo exige
  tocar archivos fuera de `touch_only`. Documentar el analisis con
  evidencia; prohibido editar el oraculo o inventar tests.
