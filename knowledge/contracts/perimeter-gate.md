---
type: 'Task Contract'
title: 'Gate de perimetro (Tocar SOLO como dato)'
description: 'Validador determinista de que los archivos cambiados por un dev efimero caen dentro del perimetro touch_only declarado en su task contract, con el oraculo congelado explicitamente fuera del perimetro. Convierte la verificacion manual del PM en maquina. Infraestructura.'
tags: ['ccdd', 'perimetro', 'gate', 'infra']

task: perimeter-gate
intent: "Validar que los archivos cambiados por una delegacion caen dentro del perimetro touch_only del contrato."
target: scripts/validate_perimeter.py
signature: "def validate_perimeter(contract_path, changed_files) -> list"
test_command: "python -m unittest tests/test_validate_perimeter.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_validate_perimeter.py"
tests_sha256: "9e36981ada785a414b01e2ecd1d64f6ccdf8bc19438424d72d17d922659a84f4"
touch_only: ['scripts/validate_perimeter.py', 'scripts/validate_contracts.py', 'tests/test_parser_coherence.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de perimetro (validate_perimeter)

## Intent
Convertir el "Tocar SOLO" de prosa en verificacion determinista (idea importada
del analisis de Shepherd: la firma como superficie de permisos, al nivel KDD =
verificacion post-hoc del diff). Dos piezas: la clave `touch_only` obligatoria
validada estructuralmente por `validate_contracts.py`, y el gate
`validate_perimeter.py` que el PM corre sobre el diff del dev.
Spec: `specs/CONTRACT-28-perimeter-gate.md`.

## Interface
- `validate_perimeter(contract_path, changed_files) -> list` — findings
  `{'file','level','rule','msg'}`; semantica y mensajes EXACTOS en el docstring
  del oraculo congelado `tests/test_validate_perimeter.py` (FM_PARSE,
  TOUCH_ONLY_MISSING, TESTS_TOUCHED con excepcion tests==target,
  OUT_OF_PERIMETER; fnmatch posix; normalizacion de paths).
- `main(argv) -> int` — `validate_perimeter.py <contract.md> [--changed ...]`,
  sin --changed lee stdin; Resumen honesto con archivos ESCANEADOS; exit 0/1.
- En `scripts/validate_contracts.py`: `touch_only` se suma a REQUIRED_KEYS
  (FM_KEY_touch_only) + checks nuevos FM_TOUCH_ONLY (forma), FM_TOUCH_TARGET
  (target cubierto), FM_TOUCH_TESTS (oraculo NO cubierto, salvo tests==target).
  Semantica exacta: clase `TestTouchOnly` de `tests/test_validate_contracts.py`.

## Invariants
- Python stdlib puro; sin red, sin subprocess (el `git diff --name-only` lo
  corre el CALLER y entra por stdin/args); determinista; mensajes ASCII.
- Parser de frontmatter: COPIA del mini-YAML (mismos 4 simbolos); la coherencia
  se fija extendiendo `tests/test_parser_coherence.py` a 4 vias (solo AGREGAR).
- En validate_contracts: SOLO agregar los checks nuevos; nada existente se
  debilita ni cambia de mensaje.

## Examples
- `validate_perimeter(c, ['src/hello.py'])` con touch_only `['src/hello.py']`
  -> `[]`.
- Cambiado `README.md` fuera del perimetro -> `OUT_OF_PERIMETER` nombrandolo.
- Cambiado el archivo `tests` del contrato -> `TESTS_TOUCHED` (sin duplicar
  OUT_OF_PERIMETER para ese archivo).

## Do / Don't
- DO: estilo de `validate_skills.py`/`validate_changelog.py`.
- DON'T: tocar `tests/test_validate_perimeter.py` (oraculo congelado, sellado).
- DON'T: debilitar `tests/test_validate_contracts.py` ni tocar otros gates.

## Tests
`python -m unittest tests/test_validate_perimeter.py` y
`python -m unittest tests/test_validate_contracts.py` verdes SIN modificar los
oraculos; `test_parser_coherence` verde a 4 vias; suite completa sin
regresiones.

## Constraints
- Tocar SOLO: `scripts/validate_perimeter.py`, `scripts/validate_contracts.py`
  (solo checks nuevos), `tests/test_parser_coherence.py` (solo extender).
  Reporte local en `.agents/logs/C28-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: los oraculos exigieran comportamiento contradictorio; la
  extension a 4 vias no pasara sin tocar los otros parsers; o el budget de
  complejidad no alcanzara sin romper un test.
