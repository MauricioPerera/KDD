# Contrato 13 — Lint ASCII de literales en scripts: la convención deja de ser inspección del PM

Prerrequisitos: contratos 01-12 cerrados, HEAD `1e7fb83`, suite 151 verde 2×, CI verde en
ambas patas. Motivación (pendiente declarado en `docs/reports/CONTRACT-12-REPORT.md`): en
C10-C12 los devs efímeros introdujeron acentos en mensajes de script 3 veces pese a la
instrucción ASCII explícita; se cazaron por inspección del PM, no por gate. RECON
(2026-07-07, inventario por `ast` de literales no-ASCII fuera de docstrings en
`scripts/*.py`): (a) `validate_contracts.py:314` tiene "inválido" con acento — una
violación REAL de la clase, viva hoy; (b) `validate_specs.py:39` usa
`'Criterios de aceptación'` — legítimo (matchea headers reales de los specs, que llevan
acentos); (c) `export_gate_contract.py` tiene 23 literales unicode en `_EXPLICIT_MAP` —
legítimos (el propósito del archivo es mapear tipográficos a ASCII).

> Capa: este es un **contrato de ejecución** (nivel proyecto). La tarea lleva su
> **task contract** CCDD en `knowledge/contracts/lint-ascii.md` (autorado por el
> orquestador, validado por `scripts/validate_contracts.py`).

Decisiones de diseño (fijadas acá): el lint excluye **docstrings** (no se imprimen; el
español con acentos es legítimo ahí) y ofrece dos escapes explícitos y visibles en
review: pragma de línea `# ascii: allow` (para literales puntuales como el de
`validate_specs.py:39`) y pragma de módulo `# ascii-lint: skip-file` en las primeras 5
líneas (para `export_gate_contract.py`, con comentario del porqué). Los comentarios del
código quedan fuera del alcance (no se imprimen). El lint se aplica a sí mismo.

## LINT-ASCII (T1) — `scripts/lint_ascii.py` + fix de la violación viva + CI

FIX/OBJETIVO:
1. `scripts/lint_ascii.py` (nuevo): recorre `scripts/*.py`, parsea con `ast` y marca ERROR
   todo literal string (incluye f-strings) con caracteres fuera de ASCII (ord > 127),
   EXCLUYENDO docstrings (primer statement string de módulo/clase/función). Cada finding
   nombra archivo, línea, el/los codepoints (formato U+XXXX) y un preview del literal.
   Escapes: línea del literal con `# ascii: allow` → se permite; archivo con
   `# ascii-lint: skip-file` en las primeras 5 líneas → se saltea (y el resumen lo
   declara: sin silencios). Findings ordenados (archivo, línea); API
   `def lint_ascii(scripts_dir: str) -> list:` con findings `{'file','level','rule','msg'}`
   y CLI espejo del estilo de `validate_okf.py`: exit 0 sin ERRORs · 1 con ≥1 ERROR.
   Stdlib puro; sin red; sin subprocess; determinista. El propio `lint_ascii.py` pasa su
   lint (mensajes ASCII).
2. Violación viva corregida: `validate_contracts.py:314` "inválido" → "invalido" (SOLO
   ese literal).
3. Legítimos marcados: pragma `# ascii: allow` en `validate_specs.py:39`;
   `# ascii-lint: skip-file` (con comentario del porqué) en `export_gate_contract.py`.
4. `tests/test_lint_ascii.py` (nuevo; reemplaza el stub sellado): fixtures en tempdir —
   literal con acento → ERROR nombrando línea y codepoint; docstring con acentos → pasa;
   literal con `# ascii: allow` → pasa; archivo con skip-file → pasa y el resumen lo
   declara; f-string con no-ASCII → ERROR; `scripts/` real del repo → limpio; exit codes
   del CLI. El dev re-sella `tests_sha256` en `knowledge/contracts/lint-ascii.md` al
   terminar (contrato de tooling: el dev autora sus tests; el sello congela el drift
   futuro, no la autoría presente).
5. CI: paso nuevo "Lint ASCII scripts" (`python scripts/lint_ascii.py scripts`) en
   `.github/workflows/validate.yml`, sin tocar los pasos existentes.

## Criterios de aceptación

- [ ] `python scripts/lint_ascii.py scripts` exit 0 sobre el repo (con el fix del punto 2
  y los pragmas del punto 3; sin ellos daría ERROR — verificado en RECON).
- [ ] Mutación (fixture): script con `"inválido"` en un literal → exit 1 nombrando línea
  y codepoint; el mismo literal con `# ascii: allow` → exit 0.
- [ ] Docstring con acentos en fixture → exit 0 (excluida).
- [ ] `python scripts/validate_contracts.py knowledge/contracts` exit 0 (incluye
  `lint-ascii.md` con `tests_sha256` re-sellado sobre los tests finales).
- [ ] `python scripts/validate_specs.py specs` exit 0 y
  `python scripts/validate_okf.py knowledge` exit 0.
- [ ] `.github/workflows/validate.yml` con el paso nuevo y
  `python -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))"` sin
  excepción; pasos existentes intactos.
- [ ] Final: `python -m unittest discover -s tests -p "test_*.py"` suite completa 2×
  verde (dos corridas idénticas); CI verde en ambas patas.

## Restricciones

- Tocar SOLO: `scripts/lint_ascii.py` (nuevo), `tests/test_lint_ascii.py` (reemplaza el
  stub), `scripts/validate_contracts.py` (SOLO el literal de la línea 314),
  `scripts/validate_specs.py` (SOLO agregar el pragma en la línea 39),
  `scripts/export_gate_contract.py` (SOLO agregar el pragma skip-file con su comentario),
  `.github/workflows/validate.yml` (SOLO agregar el paso),
  `knowledge/contracts/lint-ascii.md` (SOLO re-sellar `tests_sha256`).
- Los specs `CONTRACT-01..12` y sus reportes son históricos: read-only.
- Python stdlib puro en el target; sin red; sin subprocess en el script (los tests sí
  pueden usar subprocess para el CLI).
- NO commitear (el PM commitea por tarea verificada). Si algo no se puede sin romper otro
  criterio, PARAR y reportar.
- ABORTAR SI: el lint no puede quedar limpio sobre el repo sin marcar como allow algo que
  sea una violación real (eso es un hallazgo, no un pragma); o mantener verde un test
  existente exigiera cambios fuera del perímetro; o el paso de CI no puede añadirse sin
  tocar pasos existentes -> PARAR, documentar el porqué con evidencia en el reporte y
  marcar BLOQUEADO.

## Checklist antes de delegar

- [x] RECON corrido (2026-07-07): inventario `ast` completo de no-ASCII fuera de
  docstrings en `scripts/*.py` — exactamente 3 orígenes (violación real en
  `validate_contracts.py:314`; legítimo en `validate_specs.py:39`; 23 legítimos en la
  tabla del exportador). Suite 151 verde 2× y CI verde en ambas patas en el HEAD de
  partida. Consola Windows cp1252 reprodujo el mojibake al imprimir el inventario (la
  clase de fallo es real en este host).
- [x] Todo criterio tiene comando + resultado esperado.
- [x] Red-team hecho: un lint que siempre devuelve 0 no pasa la mutación; skip-file se
  declara en el resumen (sin exención silenciosa); el lint se aplica a sí mismo; el
  pragma queda visible en diff/review (un dev no puede colar acentos sin dejar rastro
  greppeable `# ascii: allow`).
- [x] Perímetro declarado; una sola tarea, sin concurrencia (el dev de CI no corre en
  paralelo esta vez: mismo dev toca validate.yml).
- [x] Condiciones de aborto explícitas.
