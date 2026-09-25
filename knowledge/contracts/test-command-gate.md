---
type: 'Task Contract'
title: 'Gate que ejecuta el test_command de cada contrato (Nivel 1)'
description: 'Ejecuta el test_command de cada contrato, falla ante exit code no cero y separa los resultados de producto e infraestructura.'
tags: ['ccdd', 'gate', 'infra', 'verificacion']

task: test-command-gate
intent: "Ejecutar el test_command de cada contrato de knowledge/contracts/ y fallar si algun exit code no es 0."
target: scripts/validate_test_commands.py
signature: "def run_all(contracts_dir, repo_root, timeout=180) -> list"
test_command: "python -m unittest tests/test_validate_test_commands.py"
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: "tests/test_validate_test_commands.py"
tests_sha256: "de5320b89316db118941deaec4a1aa5afd5bba92929865c9e3c17540053f6cbf"
touch_only: ['scripts/validate_test_commands.py']
deps_allowed: []
forbids: ['network', 'llm']
---

# Contract: Gate que ejecuta test_command (validate_test_commands)

## Intent
Cerrar el hueco mas critico del pipeline de verificacion de este repo:
Nivel 1 (en su momento, los gates deterministas listados en
`knowledge/validacion.md` -- hoy son 18 en total) verifica que cada
`knowledge/contracts/*.md` este bien formado — que tenga `test_command`,
`tests_sha256`, `touch_only`, etc. como texto — pero ninguno de los demas
gates corre el `test_command` declarado. Un contrato puede pasar todos los
demas gates con un `test_command` que falla, esta mal escrito, o apunta a
un archivo que no existe, y nadie lo nota salvo que un humano corra
manualmente cada comando a mano. Este gate corre el `test_command` de cada
contrato existente y reporta PASS/FAIL por contrato.

## Por que este gate rompe la convencion forbids: subprocess
La mayoria de los demas gates de Nivel 1 declaran
`forbids: [..., 'subprocess', ...]` porque para SU intent (parsear un
YAML, un JSON, un .md, un diagrama) usar `subprocess` seria una salida de
emergencia evitable — ver `knowledge/contracts/diagram-gate.md` como
ejemplo canonico de esa restriccion. Este gate es una excepcion
deliberada: su intent ES ejecutar un comando arbitrario (`test_command`,
texto libre del contrato, ej. `"python -m unittest tests/test_x.py"` o, en
un proyecto no-Python, `"npm test"`/`"cargo test"`) y leer su exit code.
No hay forma de cumplir ese intent sin `subprocess`. Por eso `forbids` en
este contrato es `['network', 'llm']` unicamente — sigue prohibiendo red y
LLM, pero no subprocess. Esta es una de dos excepciones entre los gates de
Nivel 1 (la otra es [mcp-gate-dispatch](./mcp-gate-dispatch.md), con el
mismo motivo: reusar `scripts/*.py` via subprocess ES su intent); cualquier
gate nuevo que NO sea "ejecutar el `test_command` de un contrato" o
"despachar otro gate como subprocess" debe seguir sin `subprocess`.

## Interface
- `extract_test_command(text) -> str|None` — valor de `test_command` en el
  frontmatter YAML de un contrato (comillas simples o dobles). `None` si
  la clave no esta o esta vacia.
- `collect_contracts(directory) -> [{'path','test_command','scope'}]` — un item
  por cada `*.md` de `directory` que NO empieza con `TEMPLATE-` y tiene
  `test_command` no vacio. Ordenado por `path`. `scope` es `product` o
  `infrastructure`: `test_scope` explícito prevalece; sin él, los targets en
  `scripts/`, `tools/`, `plugins/`, `.github/` o `tests/` son infraestructura
  y los demás son producto.
- `run_test_command(cmd, cwd, timeout, capture=False) -> {'exit_code','ok','error'}` —
  corre `cmd` (partido con `shlex.split`) via `subprocess.run(cwd=cwd,
  timeout=timeout)`. `error` es `None`, `'timeout'` o `'not_found'`. Con
  `capture=True` agrega `stdout` y `stderr` sin cambiar el exit code.
- `run_all(contracts_dir, repo_root, timeout=180) -> [{'path',
  'test_command','exit_code','ok','error','stdout','stderr'}]` — corre `run_test_command`
  para cada item de `collect_contracts(contracts_dir)`, mismo orden.
- `main(argv) -> int` — `argv[1]`=contracts_dir (default
  `knowledge/contracts`), `argv[2]`=repo_root (default `.`). Imprime
  `PASS [scope] <path>` o `FAIL [scope] <path>: <detalle>` por linea, y
  resumen separado para cada scope. Si no hay contratos de un scope imprime
  `SKIP [scope]`; no suma PASS. Devuelve 0 si todos
  los items de `run_all` tienen `ok is True`; 1 si alguno es `False`; 1 si
  `collect_contracts` no encuentra ningun contrato (config vacia es error,
  no exito vacuo).

## Invariants
- `run_test_command` nunca lanza excepcion: `FileNotFoundError` y
  `subprocess.TimeoutExpired` se capturan y se traducen a
  `error: 'not_found'` / `error: 'timeout'`. El CLI acepta `--timeout <segundos>`;
  el default de 180s evita confundir suites lentas conocidas con fallos, sin
  convertir un proceso colgado en éxito.
- `collect_contracts` nunca incluye `TEMPLATE-*.md` ni archivos sin
  `test_command` no vacio.
- `main` devuelve 0 unicamente si `run_all` es no vacio y todos sus items
  tienen `ok is True`.
- La salida del `test_command` se etiqueta como informativa y separada del
  resultado del gate para distinguir findings de fixtures de fallos reales.
- Un contrato de producto que falla hace fallar el gate aunque toda la
  infraestructura esté verde.
- El orden de `collect_contracts`/`run_all` es siempre por `path`
  ascendente (determinismo del reporte).

## Examples
- `extract_test_command('---\ntest_command: "python -m unittest x"\n---')`
  -> `"python -m unittest x"`.
- `collect_contracts('knowledge/contracts')` sobre el repo real -> una
  entrada por cada contrato con `test_command`, `TEMPLATE-*.md` excluidos.
- `run_test_command('python -c "import sys; sys.exit(1)"', cwd='.',
  timeout=10)` -> `{'exit_code': 1, 'ok': False, 'error': None}`.
- `main(['prog', 'knowledge/contracts', '.'])` sobre un repo con un solo
  contrato cuyo `test_command` falla -> imprime `FAIL <path>: exit_code=1`
  y devuelve 1.
- Una suite negativa que escribe `ERROR` pero termina con exit code 0 se
  reporta como `PASS` y su texto se muestra bajo `TEST_OUTPUT (informativo)`;
  el texto de la fixture nunca sustituye al veredicto del exit code.

## Do / Don't
- DO: correr cada `test_command` con un timeout explicito.
- DO: capturar `FileNotFoundError`/`TimeoutExpired` en vez de dejarlos
  propagar (un `test_command` roto no debe tumbar el gate con traceback).
- DON'T: interpretar ni validar el contenido de `test_command` (no es
  responsabilidad de este gate decidir si el comando "tiene sentido",
  solo si su exit code es 0).
- DON'T: modificar ningun contrato ni archivo fuera de
  `scripts/validate_test_commands.py`.

## Tests
(Los tests estan en `tests/test_validate_test_commands.py`, oraculo
congelado con fixtures propios via `tempfile.mkdtemp()` — no corre los
`test_command` reales del repo, eso lo hace `main()` en CI.)

## Constraints
- Sin red, sin LLM (`forbids`). `subprocess` permitido — ver seccion
  dedicada arriba.
- Solo stdlib (`deps_allowed: []`): `subprocess`, `shlex`, `os`, `re`,
  `sys`.
- `touch_only`: unicamente `scripts/validate_test_commands.py`. Tests ya
  existen y estan sellados por `tests_sha256` (Capa 0 de este contrato).
- Timeout por comando obligatorio (default 180s) para que una suite lenta conocida
  tenga margen, pero un
  `test_command` colgado no cuelgue el gate completo ni el pipeline de
  Nivel 1 en CI.
- Este gate NO reemplaza a `validate_contracts.py` (que sigue validando
  la forma del contrato); corre DESPUES, sobre contratos ya bien
  formados. Agregarlo a `GATES` en `scripts/benchmark_gates.py` y a la
  lista de `knowledge/validacion.md` es responsabilidad de una tarea
  aparte (ver `knowledge/por-que-kdd.md`), no de este contrato.
- PARAR y reportar si necesitas conectarte a la red.

## Criterios de aceptacion
- [ ] `python -m unittest tests/test_validate_test_commands.py` sale en 0.
- [ ] `python scripts/validate_test_commands.py knowledge/contracts .`
      corrido sobre el repo real imprime un veredicto PASS/FAIL por cada
      contrato con `test_command` y devuelve exit 0 si todos son PASS.
