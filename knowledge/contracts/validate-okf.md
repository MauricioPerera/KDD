---
type: 'Task Contract'
title: 'Validador OKF de la base de conocimiento'
description: 'Validador determinista de conformidad OKF para toda la KB: frontmatter, tipos, enlaces rotos y nodos huérfanos según OKF-SPEC §1-§5.'
tags: ['okf', 'validador', 'kb', 'gate']

task: validate-okf
intent: "Validar deterministicamente la conformidad OKF de todos los nodos de knowledge/ según la spec."
target: scripts/validate_okf.py
signature: "def validate_okf(knowledge_dir: str) -> list:"
test_command: "python -m unittest tests/test_validate_okf.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_validate_okf.py"
tests_sha256: "9374f08adbbb49ca85b3626aa21a36310982d4e5fe39989d435e6428dbc5b95c"
touch_only: ['scripts/validate_okf.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: validate-okf

## Intent
Convertir la [Especificación OKF](../OKF-SPEC.md) en un gate determinista sobre toda la KB
— hoy solo los contratos se validan y un nodo huérfano o con enlaces rotos pasa CI en
verde. Mismo movimiento que el test de coherencia de C02, a escala de la KB.

## Interface
```python
def validate_okf(knowledge_dir: str) -> list:
    """Valida todos los nodos .md bajo knowledge_dir según OKF-SPEC §1-§5.
    Devuelve lista de findings [{'file': str, 'level': 'ERROR'|'WARNING', 'rule': str,
    'msg': str}], vacía si la KB es conforme. No lanza ante KB inválida (reporta)."""
```
CLI: `python scripts/validate_okf.py <knowledge_dir>` — salida y resumen en el estilo de
`scripts/validate_contracts.py`; exit 0 sin ERRORs · 1 con ≥1 ERROR.

## Invariants
- Reglas: frontmatter presente y parseable con claves `type/title/description/tags`
  (`tags` lista no vacía, valores en minúsculas); `type` ∈ los 4 reconocidos de la spec;
  enlaces markdown relativos internos a `knowledge/` resuelven a un archivo `.md`
  existente o a una carpeta existente (archivo existente con otra extensión → ERROR
  nombrando archivo y extensión); todo nodo alcanzable desde `index.md` (directo o
  vía enlace a su carpeta) — huérfano = ERROR nombrando el archivo.
- `index.md` es la raíz de alcanzabilidad y no requiere frontmatter (es catálogo, no nodo).
- Determinista: findings ordenados (por archivo, luego regla); sin red, sin subprocess,
  sin reloj; stdlib puro.
- La KB actual del repo pasa limpia; si un nodo existente viola la spec, se corrige el
  nodo (reportándolo), no se relaja el check.

## Examples
- `validate_okf("knowledge")` sobre la KB actual -> `[]` (conforme) y CLI exit 0.
- KB de fixture con `solitario.md` no enlazado desde `index.md` -> finding ERROR regla
  huérfano nombrando `solitario.md`; CLI exit 1.
- Nodo con `[roto](./no-existe.md)` -> finding ERROR de enlace roto con origen y destino.
- Nodo con `[nota](./raro.txt)` donde `raro.txt` existe -> finding ERROR de enlace a
  archivo no-`.md` nombrando `raro.txt` y `.txt`; CLI exit 1.
- Nodo con `[carpeta](./data_models/)` (carpeta existente) -> sin finding (válido por §5).

## Do / Don't
- DO: reusar el enfoque de parseo de frontmatter del validador existente (mismo dialecto).
- DO: mensajes con archivo + regla + causa exacta, resumen final con conteos.
- DON'T: dependencias fuera de stdlib; red; subprocess en el target (los tests del CLI sí
  pueden usar subprocess).
- DON'T: tocar validate_contracts.py, assemble_context.py, ccdd/, src/, tests existentes.

## Tests
(Los tests están en `tests/test_validate_okf.py`: fixtures en tempdir para huérfano,
enlace roto, type inválido, frontmatter ausente/roto, tags vacías; KB real del repo pasa;
exit codes del CLI.)

## Constraints
- PARAR y reportar si... la KB actual tuviera una violación que no se pueda corregir sin
  cambiar `OKF-SPEC.md` o `index.md` estructuralmente, o si un test existente se rompiera.
