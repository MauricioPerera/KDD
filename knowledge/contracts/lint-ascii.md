---
type: 'Task Contract'
title: 'Lint ASCII de literales en scripts'
description: 'Linter determinista que exige ASCII en los literales string de scripts/*.py (docstrings excluidas), con pragmas explicitos para excepciones legitimas.'
tags: ['lint', 'ascii', 'scripts', 'gate', 'tooling']

task: lint-ascii
intent: "Convertir la convencion ASCII de los mensajes de scripts en un gate determinista, no en inspeccion del PM."
target: scripts/lint_ascii.py
signature: "def lint_ascii(scripts_dir: str) -> list:"
test_command: "python -m unittest tests/test_lint_ascii.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_lint_ascii.py"
tests_sha256: "bf7921b3b7f9fa2dd0b8a4e284e2125b080426e69eeca58ee72f9ef82e6381a4"
touch_only: ['scripts/lint_ascii.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: lint-ascii

## Intent
En C10-C12 los devs efímeros introdujeron acentos en mensajes de script 3 veces pese a la
instrucción explícita; se cazaron por inspección del PM. Mismo movimiento que
[validate-okf](./validate-okf.md) y [validate-specs](./validate-specs.md): convertir la
disciplina en gate. Contexto de proceso: [metodología de
ejecución](../metodologia-ejecucion.md).

## Interface
```python
def lint_ascii(scripts_dir: str) -> list:
    """Recorre los .py de scripts_dir y marca ERROR todo literal string con
    caracteres fuera de ASCII (ord > 127), excluyendo docstrings. Devuelve
    lista de findings [{'file','level','rule','msg'}] ordenada (archivo,
    linea), vacia si todo es conforme. No lanza ante archivos invalidos
    (reporta)."""
```
CLI: `python scripts/lint_ascii.py [scripts_dir]` — salida y resumen en el estilo de
`scripts/validate_okf.py`; exit 0 sin ERRORs · 1 con >=1 ERROR.

## Invariants
- Docstrings excluidas (primer statement string de módulo/clase/función): no se imprimen
  y el español con acentos es legítimo ahí.
- f-strings incluidas: sus partes literales también se lintean.
- Pragma de línea `# ascii: allow` (en la línea donde inicia el literal) → permitido.
- Pragma de módulo `# ascii-lint: skip-file` en las primeras 5 líneas → archivo salteado
  y DECLARADO en el resumen (sin exenciones silenciosas).
- Cada finding nombra archivo, línea, codepoint(s) en formato U+XXXX y un preview.
- El propio `lint_ascii.py` pasa su lint (mensajes ASCII).
- Determinista: findings ordenados; stdlib puro; sin red; sin subprocess; sin reloj.
- El `scripts/` real del repo pasa limpio (con el fix y los pragmas de C13).

## Examples
- `lint_ascii("scripts")` sobre el repo (post C13) -> `[]` y CLI exit 0.
- Fixture con `msg = "inválido"` -> finding ERROR nombrando la línea y `U+00E1`; exit 1.
- El mismo literal con `# ascii: allow` al final de la línea -> sin finding.
- Fixture con docstring `"""Validación básica."""` y sin otros literales -> sin finding.
- Fixture con `# ascii-lint: skip-file` en la línea 1 y literales con acentos -> sin
  finding, y el resumen declara el archivo salteado.

## Do / Don't
- DO: espejar interfaz, formato de salida y estilo de `scripts/validate_okf.py`.
- DO: mensajes con archivo + línea + codepoint + causa exacta; resumen con conteos y
  archivos salteados.
- DON'T: lintear comentarios ni identificadores (no se imprimen); dependencias fuera de
  stdlib; red; subprocess en el target (los tests del CLI sí pueden).
- DON'T: tocar validadores existentes más allá del perímetro del spec de C13.

## Tests
(Los tests están en `tests/test_lint_ascii.py`: el dev REEMPLAZA el stub sellado con la
suite real —fixtures en tempdir para violación/pragma/docstring/skip-file/f-string,
`scripts/` real limpio, exit codes del CLI— y re-sella `tests_sha256` en este contrato al
terminar. Contrato de tooling: el dev autora sus tests; el sello congela el drift futuro.)

## Constraints
- PARAR y reportar si... dejar el lint limpio sobre el repo exigiera marcar como allow
  una violación real (eso es un hallazgo, no un pragma), o si un test existente se
  rompiera con el cambio.
