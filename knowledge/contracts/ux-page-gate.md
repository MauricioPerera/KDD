---
type: 'Task Contract'
title: 'Gate de UX/accesibilidad de paginas HTML'
description: 'Validador determinista de propiedades mecanicas de una pagina HTML autocontenida: balance de tags, completitud de i18n via JSON embebido, contraste WCAG sobre pares declarados explicitamente, guarda de reduced-motion, IDs referenciados por JS. Severidad calibrada contra un tercero real (google-labs-code/design.md): referencias rotas = error, accesibilidad recomendada = warning.'
tags: ['ccdd', 'ux', 'accesibilidad', 'gate', 'infra']

task: ux-page-gate
intent: "Validar propiedades mecanicas de UX/accesibilidad de una pagina HTML, dejando el juicio estetico explicitamente fuera."
target: scripts/validate_ux_page.py
signature: "def validate_ux_page(html_path) -> list"
test_command: "python -m unittest tests/test_validate_ux_page.py"
budget:
  max_cyclomatic_complexity: 12
  max_nesting_depth: 4
tests: "tests/test_validate_ux_page.py"
tests_sha256: "aa4929a4072402f668b3a08286c8008c04d39ca1a477452a9b208cf1a0712f8b"
touch_only: ['scripts/validate_ux_page.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de UX/accesibilidad (validate_ux_page)

## Intent
Medir lo mecánico de una página HTML (balance estructural, completitud de
i18n, contraste WCAG, guarda de reduced-motion, referencias de ID) sin
navegador real — dejando explícitamente FUERA el juicio estético (misma
frontera que C23, editorial). Diseño calibrado contra un tercero real de
producción, `google-labs-code/design.md` (25k stars): fórmula WCAG verificada
independientemente contra la suya; severidad (`contrast-ratio`=warning en su
linter, solo referencias rotas=error) usada para calibrar la nuestra.
Spec: `specs/CONTRACT-30-ux-page-gate.md`.

## Interface
- `validate_ux_page(html_path) -> list` — findings `{'file','level','rule','msg'}`
  ordenados por (rule, msg). Reglas, severidad y mensajes EXACTOS: docstring
  del oráculo congelado `tests/test_validate_ux_page.py` (HTML_UNCLOSED,
  I18N_DATA_MISSING/I18N_DATA_INVALID/I18N_MISSING, ID_UNRESOLVED,
  CONTRAST_DATA_INVALID, CONTRAST_LOW, MOTION_UNGUARDED, FILE_ERROR).
- `main(argv) -> int` — uno o más paths (archivo o directorio, default
  `['examples/ux-page']`); escanea `*.html` recursivo; capa opcional
  (path ausente o sin `.html` → INFO `PATH_MISSING`, no cuenta para exit);
  exit 1 solo si hay ≥1 ERROR, WARNING nunca bloquea; Resumen honesto con
  archivos HTML efectivamente escaneados.

## Invariants
- Python stdlib puro (`html.parser`, `re`, `json`); sin red, sin subprocess,
  sin navegador; determinista; mensajes ASCII.
- Contraste: SOLO sobre pares declarados en
  `<script type="application/json" id="ux-contrast-pairs">[{"scope","text","bg"}]</script>`
  — nunca parsea CSS libre. Ausencia total del bloque = sin finding (opt-in).
- i18n: SOLO sobre `<script type="application/json" id="i18n-data">{"lang":{...}}</script>`
  — nunca un objeto JS literal (exigiría un motor JS para leerse con seguridad).
- Severidad fija: HTML_UNCLOSED/I18N_*/ID_UNRESOLVED/CONTRAST_DATA_INVALID/
  FILE_ERROR = ERROR (referencias rotas); CONTRAST_LOW/MOTION_UNGUARDED =
  WARNING (accesibilidad recomendada, no ruptura estructural).

## Examples
- Página con `data-i18n="hello"` y `#i18n-data` completo en ambos idiomas →
  `[]`.
- Par de contraste `{"scope":"dark","text":"#808080","bg":"#808080"}` → ratio
  exacto `1.00:1` → `CONTRAST_LOW` (WARNING), exit code sigue en 0.
- `@keyframes` sin `@media (prefers-reduced-motion: reduce)` →
  `MOTION_UNGUARDED` (WARNING).

## Do / Don't
- DO: estilo de `validate_skills.py`/`validate_changelog.py` (findings,
  Resumen honesto, capa opcional).
- DON'T: tocar `tests/test_validate_ux_page.py` (oráculo congelado, sellado).
- DON'T: intentar evaluar estética, tono o si el diseño "se ve bien" — eso
  queda fuera por contrato, no es una omisión.
- DON'T: requerir un navegador real, red, o ejecutar el JS de la página.

## Tests
`python -m unittest tests/test_validate_ux_page.py` verde SIN modificar el
oráculo; suite completa sin regresiones.

## Constraints
- Tocar SOLO: `scripts/validate_ux_page.py`. Reporte local en
  `.agents/logs/C30-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: el oráculo exigiera comportamiento contradictorio; la
  fórmula WCAG no pudiera implementarse determinísticamente desde hex puro;
  o el budget de complejidad no alcanzara sin romper un test.
