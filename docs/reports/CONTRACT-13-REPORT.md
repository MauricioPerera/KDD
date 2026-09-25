# CONTRACT-13 — Lint ASCII de literales en scripts — REPORT

Fecha: 2026-07-07
Spec: `specs/CONTRACT-13-lint-ascii-scripts.md` (con 1 enmienda durante la ejecución)

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| `lint_ascii.py scripts` sobre el repo | ✅ exit 0, `export_gate_contract.py` declarado como salteado (sin exención silenciosa) | corrida PM |
| Mutación (fixture propio del PM) | ✅ violación f-string L2 + literal L10 → 2 ERRORs EN ORDEN (2, 10) con codepoints U+XXXX; pragma `# ascii: allow` y docstrings con acentos → limpios | fixtures del PM, no del dev |
| Violación viva corregida | ✅ `validate_contracts.py` "inválido" → "invalido" (detectada en RECON, escapada de C12) | diff |
| Validador de contratos | ✅ exit 0 (9 contratos; `lint-ascii.md` con hash re-sellado que el PM recalculó y coincide) | corrida PM |
| Validadores specs + OKF + YAML | ✅ exit 0 / OK | corrida PM |
| Suite `unittest` | ✅ verde 2× (**168 tests**: 151 + 17) | corridas del PM sobre el estado final |
| CI | ✅ ambas patas (`ubuntu-latest` y `windows-latest`) en success, con el paso nuevo "Lint ASCII scripts" | run `28902799356` |

## LINT-ASCII / T1 (commits `57cc3f0` spec+contrato+stub oráculo · `33a6533` stub target · `239441c` implementación)

`scripts/lint_ascii.py`: `ast` sobre `scripts/*.py`; ERROR por literal string no-ASCII
(f-strings incluidas), docstrings excluidas; pragma de línea `# ascii: allow` (usado en
la constante legítima de `validate_specs.py`) y `# ascii-lint: skip-file` declarado en el
resumen (usado en el exportador, cuya tabla unicode es su propósito); findings ordenados
(archivo, línea); se auto-aplica. Paso nuevo de CI tras "Validate OKF nodes".

Primera ejecución completa del flujo post-C12: task contract autorado por el orquestador
con **stubs sellados pre-delegación** (los checks de C10 exigen que target y tests
existan; el propio gate cazó al PM commiteando el contrato sin stub del target — se
corrigió con el patrón canónico antes de delegar).

## Historia de la tarea (1 re-delegación — el contrato mandó)

1. **Entrega 1**: funcional, pero la verificación del PM encontró dos incumplimientos
   del task contract: la API devolvía una TUPLA `(findings, skipped)` contra el
   `signature: -> list` declarado (el propio docstring del dev decía "-> list de
   findings"), y el orden (archivo, línea) estaba roto — el sort parseaba `"N:"` del
   mensaje (nunca dígito → siempre 0) y las f-strings se agregaban en una segunda pasada.
2. **Re-delegación 1/2** (mismo dev, feedback exacto): `lint_ascii` devuelve solo la
   lista; `_lint_dir` privada conserva los salteados para el resumen del CLI; orden por
   tuplas `(lineno, finding)` antes de emitir, con test nuevo que lo congela.

**Enmienda 1** (verificación del PM): el fix autorizado del acento en el mensaje de
`validate_contracts.py` rompía la aserción de C12 que fijaba el texto CON acento — el
test sigue al mensaje (consecuencia forzada, cero lógica nueva). Limpieza: un script de
debug del dev (`scratchpad/`) se eliminó — no era entregable.

## Verificación final del PM (independiente del dev)

- Fixtures propios: orden (f-string L2 antes que Constant L10), pragma, docstring,
  multiarchivo — veredictos exactos; lint del repo exit 0 con salteado declarado.
- `tests_sha256` de `lint-ascii.md` recalculado por el PM → coincide con el re-sellado.
- Perímetro auditado por `git status`: 1 desvío (la aserción de C12) formalizado como
  Enmienda 1; leftover de debug eliminado.
- 3 validadores + `yaml.safe_load` → exit 0/OK; suite 2× consecutivas: 168/168 ambas.
- Ambos jobs del run `28902799356` en success (`gh run view`).
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C13-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. La clase de desvío "acentos en mensajes de script" (3 ocurrencias en C10-C12)
queda cubierta por gate en local y en ambas patas del CI.
