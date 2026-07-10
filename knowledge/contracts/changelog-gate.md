---
type: 'Task Contract'
title: 'Gate de coherencia CHANGELOG-reportes'
description: 'Validador determinista de que todo contrato con reporte en docs/reports tiene su entrada en CHANGELOG.md (y viceversa, con link y sin duplicados). Nacido del incidente real de v1.2.0: tres entradas perdidas por un replace silencioso. Infraestructura, no ejemplo.'
tags: ['ccdd', 'changelog', 'gate', 'infra']

task: changelog-gate
intent: "Validar la coherencia bidireccional entre los reportes de contratos y las entradas del CHANGELOG."
target: scripts/validate_changelog.py
signature: "def validate_changelog(changelog_path, reports_dir) -> list"
test_command: "python -m unittest tests/test_validate_changelog.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_validate_changelog.py"
tests_sha256: "9e608944105280c00ca31d1be406245c77a458fb14f00f83946701fe0df580bf"
touch_only: ['scripts/validate_changelog.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de coherencia CHANGELOG-reportes (validate_changelog)

## Intent
Convertir en gate de nivel 1 la regla operativa que dejo el incidente de
v1.2.0 (entradas de CHANGELOG perdidas por un replace que fallo en silencio):
todo `docs/reports/CONTRACT-NN-REPORT.md` exige su entrada `**Contract NN` en
`CHANGELOG.md`, y viceversa. Spec: `specs/CONTRACT-27-changelog-gate.md`.

## Interface
- `validate_changelog(changelog_path, reports_dir) -> list` — findings
  `{'file','level','rule','msg'}` ordenados por (file, rule, msg).
- `main(argv) -> int` — defaults `CHANGELOG.md docs/reports`; Resumen honesto
  (contratos verificados = NN distintos ESCANEADOS); exit 0/1.
- Reglas y semantica EXACTAS: docstring del oraculo congelado
  `tests/test_validate_changelog.py` (ENTRY_MISSING, REPORT_MISSING,
  LINK_MISSING, ENTRY_DUP; capa opcional CHANGELOG_MISSING/REPORTS_MISSING).

## Invariants
- Python stdlib puro; sin red, sin subprocess, sin LLM; determinista.
- Solo cuentan reportes con patron EXACTO `CONTRACT-<digitos>-REPORT.md` y
  entradas en lineas que EMPIEZAN con `**Contract <digitos>`.
- Mensajes ASCII (gate `lint_ascii`); archivos leidos con `encoding='utf-8'`.

## Examples
- Repo real (27 pares) -> sin ERRORs.
- Reporte CONTRACT-21 sin entrada -> `ENTRY_MISSING` nombrando "21" y el
  archivo del reporte.

## Do / Don't
- DO: estilo de `validate_skills.py` (findings, Resumen, capa opcional).
- DON'T: tocar `tests/test_validate_changelog.py` (oraculo congelado, sellado).
- DON'T: tocar el CHANGELOG real ni los reportes historicos.

## Tests
`python -m unittest tests/test_validate_changelog.py` verde SIN modificar el
oraculo; suite completa sin regresiones.

## Constraints
- Tocar SOLO: `scripts/validate_changelog.py`. Reporte local en
  `.agents/logs/C27-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: el oraculo exigiera comportamiento contradictorio; el
  formato real del CHANGELOG no fuera capturable sin tocarlo; o el budget de
  complejidad no alcanzara sin romper un test.
