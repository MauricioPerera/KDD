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
tests_sha256: "fd47d2f68c9c5a07d67edfc11d05bfd930e49ca46e675564dcdd9ccf32c7cec1"
touch_only: ['scripts/export_gate_contract.py']
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
- Caso especial `test_command`: si el contrato declara EXACTAMENTE
  `python -m unittest <archivo>.py` (4 tokens; el 4to termina en `.py`, ruta de
  archivo real — no modulo dotted), el export lo reescribe a `python <archivo>.py`
  (invocacion directa, SIN `-m unittest`). Motivo: los archivos de test Python de
  este repo son auto-ejecutables (`unittest.main()` bajo `if __name__ == "__main__":`)
  y `-m unittest` no acepta rutas con `..` (las trata como nombre de modulo y falla
  con `ValueError: Empty module name`); el gate corre con `cwd` = dir del `target`,
  que produce rutas con `..`. Para cualquier otro `test_command` (mas tokens,
  `discover`, modulo dotted, `node`, `cargo`, etc.) el runner se preserva literal.

## Examples
- Export de `knowledge/contracts/validate-user-record.md` con out-dir
  `.agents/gate-exports` -> archivo ASCII cuyo `target` es `../../src/users.py` y `tests`
  `../../tests/test_users.py`, y ambos resuelven a archivos existentes.
- Contrato sin clave `target` -> ValueError / CLI exit 2 con mensaje claro.

## Do / Don't
- DO: tabla de mapeos explicita y documentada para los caracteres tipograficos comunes.
- DO: conservar los enlaces markdown (el gate no los sigue; solo deben quedar ASCII).
- DO: antes de reescribir rutas, comparar la unidad (`ntpath.splitdrive`) de
  `--repo-root` y `--out-dir` resueltos a absolutos; si difieren, fallar como
  I/O (exit 1) nombrando ambas unidades — no como contrato invalido (exit 2).
- DON'T: modificar el contrato fuente; red; subprocess; dependencias fuera de stdlib.
- DON'T: tocar contratos existentes, validadores, ensamblador, src/, ccdd/.
- DON'T: soportar export cross-drive (rutas absolutas en el export); el gate real
  las rechaza. Se falla claro en lugar de reescribir.

## Limitaciones
- **Cross-drive no soportado (Windows).** El export reescribe `target`/`tests`
  con `os.path.relpath` entre `--repo-root` y `--out-dir`; un `relpath` entre
  `C:` y `D:` no existe en Windows (`ValueError: path is on mount 'D:', start on
  mount 'C:'`). Soportarlo exigiria rutas absolutas en el export, que el gate
  real rechaza (lint `tc-tests-frozen`). Decision de diseño: NO se soporta.
  Antes de reescribir, `cross_drive_io_error()` (funcion pura, `ntpath` explicito
  para correr en CI Linux) compara unidades; si difieren, el export lanza
  `OSError` con mensaje que nombra ambas unidades y la limitacion ("las rutas
  del export no pueden cruzar unidades de Windows"). El CLI lo mapea a exit 1
  (I/O), no a exit 2 (contrato invalido). En POSIX no hay unidades
  (`splitdrive` da `''`) -> el chequeo es no-op. Invariante: el flujo same-drive
  no cambia (mismo output byte a byte).

## Tests
(Los tests estan en `tests/test_export_gate_contract.py`: normalizacion ASCII, mapeos,
reescritura de rutas, determinismo byte a byte, frontmatter preservado, export del
contrato real de C04 con rutas que resuelven, exit codes del CLI, y cross-drive —
funcion pura `cross_drive_io_error` con paths literales estilo Windows via `ntpath`
(corre en CI Linux) + CLI en host Windows: cross-drive -> exit 1 con mensaje que nombra
ambas unidades, no exit 2. `test_command` cubre 3 casos: (1) `node --test <rel>`
preserva el runner node (no se hardcodea `python`); (2) contrato sin `test_command` -> el
export no agrega la clave; (3) caso especial `python -m unittest <archivo>.py` ->
`python <archivo>.py` (SIN `-m unittest`), verificado ademas con ejecucion real via
subprocess desde el dir del target. `discover -s tests` (>4 tokens) y modulo dotted
(sin `.py`) preservan el runner literal — confirman que el caso especial no se aplica
por encima.)

## Constraints
- PARAR y reportar si... la normalizacion ASCII destruyera informacion semantica critica
  de algun contrato existente (p. ej. un patron regex con no-ASCII significativo) o si un
  test existente se rompiera.
