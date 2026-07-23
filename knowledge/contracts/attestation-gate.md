---
type: 'Task Contract'
title: 'Gate de atestacion de reportes locales (.agents/logs, Nivel local)'
description: 'Verifica un envelope mini-YAML al tope de cada .agents/logs/<task>-REPORT.md (evidencia LOCAL, gitignorada): identidad de quien corrio el gate (agente/modelo), comando+exit_code, y dos hashes recomputables (el del propio output pegado, y el del contrato al momento de verificar). Sin esto, "verified" en el ciclo de vida del contrato era una asercion humana sin sello. NO corre en CI (la evidencia es local por diseno, igual que perimeter-gate).'
tags: ['ccdd', 'gate', 'infra', 'trazabilidad']

task: attestation-gate
intent: "Verificar que cada .agents/logs/<task>-REPORT.md tenga un envelope de atestacion completo, con hashes que recomputados coincidan con el output pegado y con el contrato verificado."
target: scripts/validate_attestation.py
signature: "def validate_directory(logs_dir, repo_root='.') -> list"
test_command: "python -m unittest tests/test_validate_attestation.py"
budget:
  max_cyclomatic_complexity: 16
  max_nesting_depth: 4
tests: "tests/test_validate_attestation.py"
tests_sha256: "8701edb282b0dd06d6cdead940d7e81ee2adec2fa8b6eb789f6ecc4abb1068ba"
touch_only: ['scripts/validate_attestation.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de atestacion (validate_attestation)

## Intent
Cerrar el gap mas estrategico identificado en la auditoria delta de KDD:
`por-que-kdd.md` vende "oraculo congelado sellado por hash" como
diferenciador frente a Spec Kit/BMAD, pero el eslabon `verified` del ciclo
de vida (`knowledge/validacion.md`, seccion de ciclo de vida) — la
afirmacion de que un agente X con modelo Y corrio el comando y dio exit
0 — no tenia hash ni identidad: era texto pegado a mano en
`.agents/logs/<task>-REPORT.md` sin ninguna verificacion mecanica. Este
gate agrega un envelope mini-YAML (mismo dialecto que el frontmatter de
los contratos) al tope de cada REPORT, y lo verifica: dos hashes
recomputables (uno liga el output pegado a lo que realmente se peg, otro
liga el reporte a la revision EXACTA del contrato que se estaba
verificando) mas la presencia de una identidad (agente, modelo) que el
gate no puede verificar mecanicamente pero si puede exigir que este
presente.

## Por que este gate NO corre en CI
`.agents/logs/` esta gitignorado a proposito (`knowledge/validacion.md`,
"Ese directorio esta gitignorado a proposito: es evidencia local, no
parte del repo"). Un CI que clona el repo desde git NUNCA va a ver estos
archivos — no hay nada que auditar ahi para un runner de CI. Este gate es
para uso LOCAL del PM en el momento de verificar una tarea (mismo
tratamiento que `scripts/validate_perimeter.py`, documentado en
`knowledge/validacion.md` como "el gate de perimetro NO es paso de CI del
repo").

## Interface
- `REQUIRED_KEYS` — tupla de las 9 claves obligatorias del envelope:
  `task`, `agent`, `model`, `command`, `exit_code`, `output_sha256`,
  `contract_sha256`, `repo_head`, `timestamp`.
- `parse_envelope(text) -> (dict|None, str)` — dict de
  `{clave: valor_string}` del bloque YAML entre los primeros dos
  delimitadores `---`, y el `body` (todo lo que sigue). `(None, text)` si
  no hay envelope valido.
- `validate_report(path, repo_root) -> [{'file','level','rule','msg'}]` —
  valida un unico REPORT. Reglas: `ENVELOPE_MISSING` (WARNING, unico
  finding si aplica), `MISSING_KEY` (ERROR, una por clave ausente/vacia),
  `TASK_MISMATCH` (ERROR, `task` no coincide con el nombre de archivo),
  `EXIT_CODE_INVALID`/`EXIT_CODE_NONZERO` (ERROR), `OUTPUT_HASH_MISMATCH`
  (ERROR), `CONTRACT_MISSING`/`CONTRACT_HASH_MISMATCH` (ERROR). Cada
  chequeo posterior a `ENVELOPE_MISSING` solo corre si sus claves
  relevantes estan presentes (evita cascadas de findings espurios desde
  una sola clave faltante).
- `validate_directory(logs_dir, repo_root='.') -> [findings]` — valida
  cada `*-REPORT.md` de `logs_dir` (no recursivo), excluye
  `TEMPLATE-REPORT.md`. Directorio inexistente -> `[]` (sin `.agents/logs/`
  local, nada que auditar, no es error).
- `main(argv) -> int` — `argv[1]`=logs_dir (default `.agents/logs`),
  `argv[2]`=repo_root (default `.`). Exit 0 si no hay ningun finding
  ERROR (los WARNING como `ENVELOPE_MISSING` NO bloquean —
  retrocompatibilidad con reportes escritos antes de este gate); 1 si
  hay >=1 ERROR.

## Invariants
- `parse_envelope` nunca lanza excepcion sobre texto arbitrario (sin
  envelope -> `(None, text)` completo, nunca crashea).
- `validate_report` sobre un REPORT sin envelope devuelve EXACTAMENTE un
  finding (`ENVELOPE_MISSING`, WARNING) — ningun otro chequeo corre.
- `validate_directory` sobre un directorio inexistente devuelve `[]`, no
  levanta `OSError`.
- `TEMPLATE-REPORT.md` siempre se excluye, sin importar su contenido.

## Examples
- Un REPORT sin envelope (texto plano, formato pre-gate) -> WARNING
  `ENVELOPE_MISSING`, exit 0 en `main` (no bloquea reportes viejos).
- Un envelope con `output_sha256` que no coincide con el hash real del
  body pegado -> ERROR `OUTPUT_HASH_MISMATCH` (alguien edito el output
  pegado despues de sellar, o el sello esta mal).
- Un envelope completo y coherente (todas las claves, ambos hashes
  calzan, `exit_code: 0`) -> `[]`, exit 0.
- `task: otra-cosa` en un archivo `hello-world-REPORT.md` -> ERROR
  `TASK_MISMATCH`.

## Do / Don't
- DO: recomputar AMBOS hashes (output y contrato) con la misma
  normalizacion LF que `validate_contracts.py --hash` usa para
  `tests_sha256` — coherencia de convencion en todo el repo.
- DO: tratar `ENVELOPE_MISSING` como WARNING, no ERROR — reportes escritos
  antes de este gate no deben romper retroactivamente.
- DON'T: intentar verificar `agent`/`model`/`timestamp`/`repo_head` mas
  alla de su presencia — son atestacion (afirmacion), no verificables
  mecanicamente por este gate.
- DON'T: agregar este gate a `.github/workflows/validate.yml` — la
  evidencia que audita es local y gitignorada, un runner de CI nunca la
  ve.

## Tests
(Los tests estan en `tests/test_validate_attestation.py`, oraculo
congelado con fixtures propios via `tempfile.mkdtemp()`.)

## Constraints
- Sin red, sin subprocess, sin LLM (`forbids`).
- Solo stdlib (`deps_allowed: []`): `hashlib`, `os`, `re`, `sys`.
- `touch_only`: unicamente `scripts/validate_attestation.py`.
- No es paso de CI (ver seccion dedicada arriba); es herramienta de
  verificacion local del PM, mismo tratamiento que `validate_perimeter.py`.
- PARAR y reportar si necesitas conectarte a la red.

## Criterios de aceptacion
- [ ] `python -m unittest tests/test_validate_attestation.py` sale en 0.
- [ ] `python scripts/validate_attestation.py .agents/logs .` corrido
      sobre el repo real no lanza excepcion (el directorio puede no
      existir o estar vacio localmente; eso es valido, exit 0).
