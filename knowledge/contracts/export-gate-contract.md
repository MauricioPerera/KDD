---
type: 'Task Contract'
title: 'Exportador de contratos para el gate CCDD nivel 2'
description: 'Exporta un task contract KDD a su variante gate-nativa: normalizacion ASCII y rutas target/tests relativas al export.'
tags: ['ccdd', 'gate', 'nivel-2', 'export']

task: export-gate-contract
intent: "Exportar un task contract KDD a una variante ASCII con rutas relativas al export para el gate CCDD nivel 2."
target: scripts/export_gate_contract.py
signature: "def export_gate_contract(contract_path: str, out_dir: str, repo_root: str = '.') -> str:"
test_command: "python -m unittest tests/test_export_gate_contract.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_export_gate_contract.py"
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: export-gate-contract

## Intent
Puente determinista entre los contratos KDD (espanol con acentos, rutas relativas a la
raiz) y el gate CCDD nivel 2 real (exige ASCII estable y rutas relativas al .md del
contrato) — hallazgos de la sonda documentados en `specs/CONTRACT-05-gate-nivel-2.md`.
Contexto de metodologia: [metodologia-ejecucion](../metodologia-ejecucion.md).

## Interface
```python
def export_gate_contract(contract_path: str, out_dir: str, repo_root: str = '.') -> str:
    """Lee el contrato KDD (UTF-8), emite <out_dir>/<task>.md gate-nativo y devuelve la
    ruta escrita. Transformaciones: (1) normalizacion ASCII de TODO el texto (NFKD sin
    diacriticos; mapeos explicitos: em/en-dash -> '-', flecha -> '->', <= >= comillas
    tipograficas y bullets a ASCII; resto no-ASCII se elimina); (2) target y tests del
    frontmatter reescritos relativos a out_dir (separador '/'); (3) resto verbatim.
    Determinista: mismo input -> bytes identicos. ValueError si falta frontmatter o las
    claves task/target/tests. repo_root (default '.', resuelto a absoluto) es la raiz
    del repo (convencion KDD): las rutas target/tests del contrato se interpretan
    relativas a el; pasado explicito, el export es INDEPENDIENTE del cwd de invocacion."""
```
CLI: `python scripts/export_gate_contract.py <contrato.md> [--out-dir .agents/gate-exports] [--repo-root .]`
-> imprime la ruta escrita. Exit 0 ok · 1 I/O · 2 contrato invalido.

## Invariants
- Salida 100 % ASCII (todo byte < 128), verificable mecanicamente.
- `signature`, `test_command` y claves del frontmatter preservadas (solo target/tests
  cambian de valor; el orden de claves y secciones se preserva).
- Reescritura de rutas correcta desde cualquier out_dir (usa rutas relativas POSIX).
- Idempotente y determinista: exportar dos veces -> bytes identicos; exportar el export
  -> ASCII estable.
- stdlib puro; sin red; sin subprocess; escribe SOLO dentro de out_dir.

## Examples
- Export de `knowledge/contracts/validate-user-record.md` con out-dir
  `.agents/gate-exports` -> archivo ASCII cuyo `target` es `../../src/users.py` y `tests`
  `../../tests/test_users.py`, y ambos resuelven a archivos existentes.
- Contrato sin clave `target` -> ValueError / CLI exit 2 con mensaje claro.

## Do / Don't
- DO: tabla de mapeos explicita y documentada para los caracteres tipograficos comunes.
- DO: conservar los enlaces markdown (el gate no los sigue; solo deben quedar ASCII).
- DON'T: modificar el contrato fuente; red; subprocess; dependencias fuera de stdlib.
- DON'T: tocar contratos existentes, validadores, ensamblador, src/, ccdd/.

## Tests
(Los tests estan en `tests/test_export_gate_contract.py`: normalizacion ASCII, mapeos,
reescritura de rutas, determinismo byte a byte, frontmatter preservado, export del
contrato real de C04 con rutas que resuelven, exit codes del CLI.)

## Constraints
- PARAR y reportar si... la normalizacion ASCII destruyera informacion semantica critica
  de algun contrato existente (p. ej. un patron regex con no-ASCII significativo) o si un
  test existente se rompiera.
