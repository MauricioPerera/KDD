---
type: 'Task Contract'
title: 'Gate de formato de mensaje de commit'
description: 'Validador determinista del formato de un mensaje de commit contra Conventional Commits + reglas por defecto de commitlint (no inventadas). Herramienta opt-in de plantilla: NO es gate de CI de este repo, cuyo propio historial no sigue esta convencion.'
tags: ['ccdd', 'git', 'gate', 'infra']

task: commit-message-gate
intent: "Validar el formato de un mensaje de commit contra una convencion configurable, sin verificar su contenido ni si el commit merece existir."
target: scripts/validate_commit_message.py
signature: "def check_commit_message(msg, config) -> list"
test_command: "python -m unittest tests/test_validate_commit_message.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_validate_commit_message.py"
tests_sha256: "7ad8d52b81cdb2cbcf18751e90e3ae553b42e4676bc7e5860e3a77f90e40bee0"
touch_only: ['scripts/validate_commit_message.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de formato de mensaje de commit (validate_commit_message)

## Intent
Medir lo mecánico de un mensaje de commit (gramática Conventional Commits,
tipo conocido, línea en blanco antes del cuerpo) — nunca si el mensaje
explica bien el *por qué*, ni si el commit merece existir. Calibrado contra
un estándar público real (Conventional Commits v1.0.0) y las reglas por
defecto de `commitlint`, misma disciplina que C28/C30. Herramienta opt-in:
NO se vuelve gate de CI de este repo (el historial propio de KDD no sigue
esta convención). Spec: `specs/CONTRACT-31-commit-message-gate.md`.

## Interface
- `parse_commit_message(msg) -> dict | None` — `{'type','scope','breaking',
  'description','header','body'}`, o `None` si el header no matchea la
  gramática `tipo(scope)?!?: descripción` en absoluto.
- `check_commit_message(msg, config) -> list` — findings `{'level','rule','msg'}`
  (sin `'file'`). `config`: `{'types':[...], 'scope_required':bool,
  'max_subject_length':int}`. Reglas, severidad y mensajes EXACTOS:
  docstring del oráculo congelado `tests/test_validate_commit_message.py`.
- `main(argv) -> int` — `<config.json> [--message <texto> | --file <path> | stdin]`;
  exit 1 si ≥1 ERROR (incluido config ausente/inválido); WARNING nunca bloquea.

## Invariants
- Python stdlib puro (`re`, `json`); sin red, sin subprocess, sin llamadas a
  `git`; determinista; mensajes ASCII.
- No verifica si el commit "merece" existir ni si el mensaje explica bien el
  motivo — eso es juicio, declarado fuera.
- No verifica breaking changes reales (exigiría el diff, no solo el texto).

## Examples
- `check_commit_message("feat(gate): agrega validador", config)` → `[]`.
- `check_commit_message("banana: algo raro", config)` → `TYPE_UNKNOWN` (ERROR).
- Header de 80 caracteres → `SUBJECT_TOO_LONG` (WARNING), no bloquea.

## Do / Don't
- DO: estilo de `validate_changelog.py` (findings, Resumen honesto).
- DON'T: tocar `tests/test_validate_commit_message.py` (oráculo congelado).
- DON'T: agregar un paso de CI en `.github/workflows/validate.yml`.
- DON'T: invocar `git` ni leer `.git/` — el mensaje entra como texto.

## Tests
`python -m unittest tests/test_validate_commit_message.py` verde SIN
modificar el oráculo; suite completa sin regresiones.

## Constraints
- Tocar SOLO: `scripts/validate_commit_message.py`. Reporte local en
  `.agents/logs/C31-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: el oráculo exigiera comportamiento contradictorio; o
  el budget de complejidad no alcanzara sin romper un test.
