# fix/mcp-boundary — REPORT

Fuga de confinamiento en las tools MCP: `mcp_server.py` y `mcp_gate_dispatch.py`
reciben paths del cliente (`dir`/`dirs`/`root`/`tests_path`/`repo_root`/
`contracts_dir`/`logs_dir`) y los pasaban a `subprocess.run` (como `cwd` o
`argv`) / hashing **sin confinarlos al repo**. Un cliente MCP comprometido podía
leer o hashear archivos arbitrarios del host fuera del repo, o correr un
`test_command` con `cwd` arbitrario. No era RCE (`shell=False`, argv lista): era
fuga de confinamiento.

## Fix

Todo path que llega del cliente se confina al `repo_root` real **antes** de
cualquier `subprocess.run` / `open()` / hash. Si `os.path.realpath` del path
resuelve fuera de `repo_root`, la tool lo **rechaza** con un dict de error claro
(`exit_code: 2` + `stderr`) **sin ejecutar nada** — ni subprocess, ni hash. Un
path normal dentro del repo se despacha y corre el gate igual que antes.

Confinamiento en **dos capas** (defensa en profundidad):

1. **`scripts/mcp_server.py`** (boundary real del cliente, libre de contrato):
   `_within` / `_confine` / `_dispatch`. Toda tool de gate pasa por `_dispatch`,
   que confina cada param del dict contra `REPO_ROOT` antes de llamar a
   `gd.run_gate`. `seal_tests` confina `tests_path` antes de `gd.seal_tests`.
2. **`scripts/mcp_gate_dispatch.py`** (módulo puro, en `touch_only` del contrato
   sellado): `_within` / `_confine_params`. `run_gate` y `seal_tests` confinan sus
   params contra el `repo_root` que recibieron. Protege a cualquier caller
   directo del módulo, no solo al wiring MCP.

### Por qué tocar `mcp_gate_dispatch.py` no rompe el sello CCDD

- `touch_only: ['scripts/mcp_gate_dispatch.py']` — el contrato **permite** editar
  este archivo; lo que congela es `tests_sha256` (el archivo de **tests**), que
  **no se tocó**. Verificado: `gd.seal_tests('tests/test_mcp_gate_dispatch.py')`
  sigue devolviendo `b8075cf1727f291316af089ba31680fa0c8c155a21ebd5ff1976151c615e01e9`
  — idéntico al `tests_sha256` del contrato `mcp-gate-dispatch.md`.
- El contrato lista `os` como stdlib permitido (`Solo stdlib (deps_allowed: []):
  subprocess, sys, os, re`). Se añadió solo `import os` (más `_within` /
  `_confine_params`, stdlib puro). `validate_contracts` solo exige que
  `deps_allowed` **exista** como clave de frontmatter; no analiza los imports
  del `.py`. `lint_ascii` pasa (los string literals nuevos son ASCII; las
  docstrings están excluidas).
- Se preservaron los **invariables** del contrato: `run_gate` sigue sin lanzar
  (el rechazo devuelve un dict, no raise); `build_argv` intacto (nunca une
  listas con espacios); `run_all_level1` sigue excluyendo `validate_attestation`.
  La firma `run_gate(tool_name, params, repo_root='.', timeout=120)` no cambió.

### Semántica del confinamiento

- `os.path.join(repo_root, path)` + `os.path.realpath`. Un path relativo con
  `..` que sube fuera del repo → rechazado. Un path **absoluto** fuera del repo
  → `os.path.join` descarta `repo_root`, `realpath` cae fuera → rechazado. Un
  absoluto **dentro** del repo → aceptado. Un symlink interno que apunta fuera
  → `realpath` lo resuelve fuera → rechazado.
- Un path **inexistente pero léxicamente dentro** del repo → **aceptado**
  (confinamiento de frontera, no de existencia): el gate propio reporta si
  falta. Esto preserva los tests existentes (e.g. `dir='does/not/exist'` sigue
  dando `exit_code != 0` desde el gate, no un rechazo de confinamiento).

### Trade-offs

- **`exit_code: 2` como código de rechazo**, distinto del `0`/`!=0` propio del
  gate y del `None` de timeout. La tool NO marca `isError` (consistente con
  cómo los gates ya reportan fallos vía `exit_code`, no vía `isError`): el
  cliente ve `exit_code: 2` + `stderr` claro. Política deliberada: un rechazo
  de confinamiento es un veredicto de la tool, no un crash del protocolo.
- No se **re-escriben** los paths (no se "clampean" al repo): se rechazan. Es lo
  que pide el objetivo ("rechazarlo con un error claro en vez de ejecutar
  nada"), y evita silently hacer algo distinto de lo que pidió el cliente.
- `validate_test_commands` tiene un `root` (cwd de los `test_command`) que el
  cliente puede pasar; queda confinado a `REPO_ROOT`. Su default `'.'`
  (== `REPO_ROOT`) sigue funcionando.

## Hecho — verificación real

### 1) `python -m unittest tests/test_mcp_gate_dispatch.py -v` (suite sellada, intacta)

```
Ran 17 tests in 2.039s

OK
```

### 2) `python -m unittest tests/test_mcp_server_smoke.py -v` (con 4 tests nuevos)

```
Ran 8 tests in 0.336s

OK
```

Tests nuevos: `test_gate_rejects_dir_escaping_repo`,
`test_gate_rejects_list_dir_escaping_repo`,
`test_gate_accepts_explicit_dir_inside_repo`,
`test_seal_tests_rejects_path_escaping_repo`.

### 3) `python scripts/preflight.py` (mismo resultado que al arrancar: 19/19)

```
scan_secrets: PASS
validate_attestation: PASS
Summary: 19/19
```

### 4) Demostración concreta: path que escapa → rechazado; path normal → funciona

Tres capas (boundary MCP `_dispatch`, módulo puro `gd.run_gate`/`gd.seal_tests`,
y protocolo MCP real `tools/call`), salida real:

```
REPO_ROOT = C:\Users\Administrador\Desktop\kdd-wt-mcp

--- capa mcp_server._dispatch (boundary MCP) ---
dir=escape rel : {'exit_code': 2, 'stdout': '', 'stderr': "rejected: dir='..\\..\\..\\..\\..\\..\\etc' escapes repo_root='C:\\Users\\Administrador\\Desktop\\kdd-wt-mcp'"}
dir=escape abs : {'exit_code': 2, 'stdout': '', 'stderr': "rejected: dir='C:\\Windows\\System32\\drivers\\etc\\hosts' escapes repo_root='C:\\Users\\Administrador\\Desktop\\kdd-wt-mcp'"}
dir=normal     : {'exit_code': 0, 'stderr': ''}

--- capa gd.run_gate (defensa en profundidad, modulo puro) ---
dir=escape rel : {'exit_code': 2, 'stdout': '', 'stderr': "rejected: dir='..\\..\\..\\..\\..\\..\\etc' escapes repo_root='C:\\Users\\Administrador\\Desktop\\kdd-wt-mcp'"}
dir=normal     : {'exit_code': 0, 'stderr': ''}

--- gd.seal_tests ---
tests_path=escape : {'hash': None, 'exit_code': 2, 'stdout': '', 'stderr': "rejected: tests_path='..\\..\\..\\..\\..\\..\\etc\\passwd' escapes repo_root='C:\\Users\\Administrador\\Desktop\\kdd-wt-mcp'"}
tests_path=normal : {'hash': 'b8075cf1727f291316af089ba31680fa0c8c155a21ebd5ff1976151c615e01e9', 'exit_code': 0}

--- protocolo MCP real (tools/call) ---
validate_contracts dir=escape : {'exit_code': 2, 'stdout': '', 'stderr': "rejected: dir='..\\..\\..\\..\\..\\..\\etc' escapes repo_root='C:\\Users\\Administrador\\Desktop\\kdd-wt-mcp'"}
lint_ascii dir=scripts        : {'exit_code': 0, 'stdout': 'OK: todos los scripts son ASCII-conformes\n\nArchivos salteados (# ascii-lint: skip-file): export_gate_contract.py, vendor/codex-security/finalize_scan_contract.py, vendor/codex-security/report_projection.py, vendor/codex-security/validate_report_format.py, vendor/codex-security/windows_scan_local_files.py\n\nResumen: 0 error(es) en 33 archivo(s)\n', 'stderr': ''}
```

- `dir='..\\..\\..\\..\\..\\..\\etc'` (relativo que escapa) → `exit_code: 2`,
  rechazado, **sin** correr el gate.
- `dir='C:\\Windows\\System32\\drivers\\etc\\hosts'` (absoluto fuera del repo,
  equivalente Windows de "../../../etc") → `exit_code: 2`, rechazado.
- `dir='knowledge/contracts'` / `dir='scripts'` (normal dentro del repo) →
  `exit_code: 0`, el gate corre normalmente.
- `seal_tests` con `tests_path` que escapa → `hash: None`, `exit_code: 2`,
  rechazado; con `tests_path` normal → `hash` = `b8075cf1...` que **coincide**
  con el `tests_sha256` del contrato sellado (el sello sigue válido).

## Archivos tocados

- `scripts/mcp_server.py` — helpers `_within`/`_confine`/`_dispatch`, todas las
  tools de gate via `_dispatch`, `seal_tests` confina `tests_path`.
- `scripts/mcp_gate_dispatch.py` — `import os`, `_within`/`_confine_params`,
  confinamiento en `run_gate` y `seal_tests`.
- `tests/test_mcp_server_smoke.py` — 4 tests de confinamiento (sin tocar
  `tests/test_mcp_gate_dispatch.py` ni `knowledge/contracts/*.md`).