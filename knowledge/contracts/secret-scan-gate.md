---
type: 'Task Contract'
title: 'Gate de secretos filtrados en codigo generado (Nivel 1)'
description: 'Escaneo determinista (regex stdlib, sin red/subprocess/LLM) de src/ (extensible a otros directorios) buscando prefijos de credenciales conocidas (AWS, GitHub, Slack, Google, Stripe) y bloques de private key. NO deteccion de alta entropia generica, para no generar falsos positivos masivos contra los tests_sha256 de 64 hex chars que ya viven en knowledge/contracts/*.md de este mismo repo.'
tags: ['ccdd', 'gate', 'infra', 'seguridad']

task: secret-scan-gate
intent: "Detectar credenciales filtradas (prefijos de proveedores conocidos + bloques private key) en el codigo generado por agentes, con regex deterministico."
target: scripts/scan_secrets.py
signature: "def scan_directory(directory, extensions=('.py','.js','.ts','.md','.json')) -> list"
test_command: "python -m unittest tests/test_scan_secrets.py"
budget:
  max_cyclomatic_complexity: 12
  max_nesting_depth: 3
tests: "tests/test_scan_secrets.py"
tests_sha256: "80f2f34e67ada579b5f3a2fe023bf34b1f0ba19e1044945085f2a10174dd3dc7"
touch_only: ['scripts/scan_secrets.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de secretos (scan_secrets)

## Intent
Cerrar el gap de seguridad mas barato de cerrar de los identificados en la
auditoria tecnica de KDD: los agentes generan codigo y nada en Nivel 1
detecta una API key filtrada. `scan_dependencies` (deteccion de
dependencias vulnerables) es Nivel 2/MCP y Python-only; secret-scanning
por prefijo de proveedor es, en cambio, tan determinista y barato como
`lint_ascii.py` — regex stdlib puro, sin red, sin base de datos externa.

Deliberadamente NO usa deteccion de alta entropia generica (heuristica
comun en herramientas como `gitleaks`/`trufflehog`): este repo ya tiene
decenas de strings hex de 64 caracteres (`tests_sha256`) en
`knowledge/contracts/*.md` que serian falsos positivos masivos bajo esa
heuristica. En cambio, usa patrones de PREFIJO especificos por proveedor
(`AKIA` de AWS, `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` de GitHub, `xox[baprs]-`
de Slack, `AIza` de Google, `sk_live_`/`pk_live_` de Stripe,
`-----BEGIN ... PRIVATE KEY-----`) — el mismo enfoque de baja tasa de falso
positivo que usan los secret scanners de referencia para sus reglas mas
confiables.

## Interface
- `PATTERNS` — lista `(rule_name, compiled_regex)` de los 6 patrones.
- `scan_text(text) -> [{'rule','match','line'}]` — matches de `PATTERNS`
  sobre un string, con numero de linea 1-indexed.
- `scan_file(path) -> [{'file','level','rule','msg'}]` — findings ERROR
  de `scan_text` sobre un archivo (UTF-8, `errors='ignore'`). El `msg`
  NUNCA incluye el secreto completo (solo los primeros 8 caracteres +
  `'...'`) para no filtrarlo en logs de CI.
- `scan_directory(directory, extensions=('.py','.js','.ts','.md','.json'))
  -> [{'file','level','rule','msg'}]` — recorre recursivamente, ignora
  directorios ocultos (`.git`, etc.), `__pycache__` y `node_modules`.
  Directorio inexistente -> `[]` (no es error del gate).
- `main(argv) -> int` — `argv[1:]` son directorios a escanear (default
  `['src']`). Imprime cada finding y devuelve 0/1.

## Invariants
- `scan_text` nunca falla con una excepcion sobre texto arbitrario
  (incluye texto sin ninguno de los patrones -> `[]`).
- Ningun `tests_sha256` (hex de 64 chars) de este mismo repo dispara un
  finding — verificado explicitamente en el oraculo
  (`test_sha256_hash_is_not_flagged`).
- `scan_file` sobre un archivo binario no lanza excepcion (puede o no
  encontrar matches falsos, pero no rompe el gate).
- `scan_directory` sobre un directorio inexistente devuelve `[]`, no
  levanta `OSError`.

## Examples
- `scan_text("key = 'AKIAABCDEFGHIJKLMNOP'")` -> un finding
  `{'rule': 'AWS_KEY', 'line': 1, 'match': 'AKIAABCDEFGHIJKLMNOP'}`.
- `scan_text("tests_sha256: \"e0ef690c...90a9\"")` (64 hex chars) -> `[]`.
- `scan_directory('src')` sobre un directorio con una private key
  pegada en un `.py` -> un finding `PRIVATE_KEY_BLOCK`.
- `main(['prog', 'src', 'tests'])` sin secretos -> imprime nada, exit 0.

## Do / Don't
- DO: usar patrones de prefijo especificos por proveedor (baja tasa de
  falso positivo).
- DO: truncar el secreto en el mensaje del finding (nunca lockearlo
  completo en un log de CI).
- DON'T: usar deteccion de alta entropia generica (falsos positivos
  masivos contra los hashes legitimos de este repo).
- DON'T: escanear `knowledge/contracts/` por default (ahi viven los
  `tests_sha256` legitimos); el default es solo `src`, extensible por
  argumento si un proyecto instanciado quiere escanear otros dirs.

## Nota: por que el default es solo `src/` (y el CI de ESTE repo tambien)
El default del script es solo `['src']` precisamente por el caso de
auto-referencia: `tests/test_scan_secrets.py` (el oraculo de ESTE gate)
contiene fixtures con la FORMA exacta de los patrones
(`AKIAABCDEFGHIJKLMNOP`, bloques `-----BEGIN...PRIVATE KEY-----`, etc.) y
se hereda en TODO proyecto instanciado del template (no esta en el
MANIFEST de `scripts/init_project.py`), asi que escanear `tests/` por
default dispararia el gate contra sus propios fixtures como falsos
positivos en cualquier proyecto recien instanciado. El step de CI de
este repo invoca `python scripts/scan_secrets.py src` explicitamente por
el mismo motivo (aunque el default ya coincide). Un proyecto
instanciado que quiera escanear mas directorios los pasa como
argumento: el default se mantuvo deliberadamente estrecho para que la
primera corrida sin argumentos no se auto-detecte.

## Tests
(Los tests estan en `tests/test_scan_secrets.py`, oraculo congelado con
fixtures propios via `tempfile.mkdtemp()` — ninguno usa una credencial
real, solo cadenas con la FORMA correcta del patron.)

## Constraints
- Sin red, sin subprocess, sin LLM (`forbids`).
- Solo stdlib (`deps_allowed: []`): `os`, `re`, `sys`.
- `touch_only`: unicamente `scripts/scan_secrets.py`.
- Este gate es Nivel 1 pero OPCIONAL/no bloqueante hasta que un usuario lo
  quiera obligatorio: no se agrega a `benchmark_gates.py` por el mismo
  motivo que `test-command-gate` (oraculo de `benchmark_gates.py` ya
  sellado con conteo fijo de gates); se documenta en
  `knowledge/validacion.md` y se agrega como step de CI.
- PARAR y reportar si necesitas conectarte a la red.

## Criterios de aceptacion
- [ ] `python -m unittest tests/test_scan_secrets.py` sale en 0.
- [ ] `python scripts/scan_secrets.py src` corrido sobre el repo
      real (sin secretos reales) devuelve exit 0.
