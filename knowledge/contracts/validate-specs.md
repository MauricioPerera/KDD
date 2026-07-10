---
type: 'Task Contract'
title: 'Validador de contratos de ejecución (specs)'
description: 'Validador determinista de specs/CONTRACT-*.md: criterios por máquina, perímetro y condiciones de aborto, con la regla abierto/cerrado según docs/reports/CONTRACT-NN-REPORT.md.'
tags: ['specs', 'validador', 'gate', 'ccdd']

task: validate-specs
intent: "Convertir el checklist pre-delegación de specs/TEMPLATE-CONTRACT.md en un gate determinista sobre specs/CONTRACT-*.md, no en disciplina del redactor."
target: scripts/validate_specs.py
signature: "def validate_specs(specs_dir: str) -> list:"
test_command: "python -m unittest tests/test_validate_specs.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_validate_specs.py"
tests_sha256: "b28f6f6fef69e924a7bbc741b4cf00ea6fe1110d9c72e9d51ecfb41fe91106b3"
touch_only: ['scripts/validate_specs.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: validate-specs

## Intent
Que ningún contrato de ejecución nuevo llegue a CI sin criterios verificables por
máquina, perímetro declarado y condiciones de aborto explícitas. Hoy ese checklist
es manual en `specs/TEMPLATE-CONTRACT.md`; este contrato lo convierte en check
determinista que lo exige el validador, no la memoria del PM. Mismo movimiento que
`validate-okf` y `validate_contracts`, a escala de `specs/`.

## Interface
```python
def validate_specs(specs_dir: str) -> list:
    """Valida todos los CONTRACT-*.md bajo specs_dir. Devuelve lista de findings
    [{'file': str, 'level': 'ERROR'|'WARNING', 'rule': str, 'msg': str}],
    vacía si todos los contratos son conformes. No lanza ante specs inválidas
    (reporta). TEMPLATE-*.md se ignora."""
```
CLI: `python scripts/validate_specs.py <specs_dir>` — salida y resumen en el estilo
de `scripts/validate_okf.py`; exit 0 sin ERRORs · 1 con ≥1 ERROR.

## Invariants
- CERRADO vs ABIERTO: un contrato está CERRADO si existe
  `docs/reports/CONTRACT-NN-REPORT.md` (junto al padre del dir de specs) con su
  mismo prefijo `CONTRACT-NN`; si no, ABIERTO. `TEMPLATE-*.md` se ignora.
- Reglas para TODO contrato: sección `## Criterios de aceptación` presente con
  ≥1 checkbox (`- [ ]` o `- [x]`) que contenga un comando entre backticks;
  sección `## Restricciones` presente.
- Reglas SOLO para ABIERTOS: `Tocar SOLO` presente en Restricciones; bullet
  `- ABORTAR SI` presente y su texto (incluidas sus líneas de continuación
  indentadas hasta el siguiente bullet o sección) no contiene placeholders de
  ángulo (patrón `<...>`).
- Los contratos históricos 01-08 (cerrados) pasan sin editarse; el validador se
  adapta a ellos vía la regla cerrado/abierto, no al revés.
- Determinista: findings ordenados (por archivo, luego regla); sin red, sin
  subprocess, sin reloj; stdlib puro.

## Examples
- `validate_specs("specs")` sobre el repo actual -> `[]` (los 8 cerrados + el 09
  abierto conforme) y CLI exit 0.
- Fixture abierto sin bullet `ABORTAR SI` -> finding ERROR regla `ABORTAR`; CLI
  exit 1.
- Fixture abierto con `- ABORTAR SI: <condición>` (placeholder `<...>`) ->
  finding ERROR regla `ABORTAR`; CLI exit 1.
- Fixture abierto con `- ABORTAR SI: ... -> PARAR y reportar.` (flecha sin
  placeholder) -> sin finding; CLI exit 0.
- Fixture abierto sin comando entre backticks en criterios -> finding ERROR regla
  `SEC_CRITERIOS`; CLI exit 1.
- Fixture cerrado sin `Tocar SOLO` ni `ABORTAR SI` -> sin finding (válido).
- `TEMPLATE-CONTRACT.md` con placeholders -> sin finding (ignorado).

## Do / Don't
- DO: espejar la interfaz y el estilo de `scripts/validate_okf.py` (stdlib, sin
  red, sin subprocess; findings por archivo; resumen final con conteos).
- DO: mensajes con archivo + regla + causa exacta.
- DON'T: dependencias fuera de stdlib; red; subprocess en el target (los tests
  del CLI sí pueden usar subprocess).
- DON'T: tocar `specs/CONTRACT-01..08`, sus reportes, `validate_contracts.py`,
  `validate_okf.py`, `assemble_context.py` u otros tests existentes.

## Tests
(Los tests están en `tests/test_validate_specs.py`: fixtures en tempdir con
`docs/reports/` simulado para repo real en verde, abierto completo en verde,
abierto sin ABORTAR SI falla, abierto con placeholder en ABORTAR SI falla,
abierto sin comando entre backticks falla, cerrado sin ABORTAR SI ni Tocar SOLO
pasa, TEMPLATE ignorado; exit codes del CLI.)

## Constraints
- PARAR y reportar si... alguna regla del contrato resulta imposible de cumplir
  manteniendo verdes los contratos históricos 01-08 sin editarlos; o el paso
  nuevo de CI no puede añadirse sin tocar pasos existentes; o el task contract
  no puede pasar `validate_contracts` por una exigencia del formato que entre en
  conflicto con esta tarea. En ese caso documentar el porqué con evidencia en
  `VALIDATE-SPECS-REPORT.md` y marcar BLOQUEADO.