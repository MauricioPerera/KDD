# CONTRACT-08 — Export cross-drive: fallo honesto — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-08-export-cross-drive.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Validador de contratos | ✅ | `Resumen: 0 error(es), 0 warning(s) en 7 archivo(s)` |
| Suite `unittest` | ✅ verde 2× (121 tests, +5 vs C07) | corridas del PM sobre el estado final |
| Cross-drive → I/O honesto | ✅ | repro del PM: `ERROR (I/O): ... unidad 'D:' ... unidad 'C:'`, exit 1 |
| Función pura testeable en Linux | ✅ | tests vía `ntpath` en `test_export_gate_contract.py` (22 verdes) |
| Invariante same-drive | ✅ | `cmp` byte-idéntico (evidencia en reporte del dev, con stash) |
| CI | ✅ | run verde sobre el push de cierre |

## EXPORT-XDRIVE / T10 (commit `c7cb58d`)

Decisión de diseño (fijada en el spec): el export cross-drive NO se soporta — un relpath
entre unidades de Windows no existe y rutas absolutas en el export las rechaza el gate real.
El script ahora compara unidades (`splitdrive`) de `--repo-root` y `--out-dir` resueltos,
mediante la función pura `cross_drive_io_error()` (no-op en POSIX, testeable con paths
literales vía `ntpath` para que el caso Windows corra en el CI Linux). Si difieren: error de
I/O que nombra ambas unidades y sugiere la corrección, exit 1 (convención I/O del script) —
ya no el engañoso "ERROR (contrato invalido)" exit 2. Task contract
`export-gate-contract.md` documenta la limitación.

## Verificación final del PM (independiente del dev)

- Repro original del PM (la que destapó el bug en C07):
  `python scripts/export_gate_contract.py knowledge/contracts/init-project.md --repo-root . --out-dir <dir en C:>`
  → mensaje nuevo de I/O nombrando 'D:' y 'C:', `EXIT=1`.
- `python -m unittest tests/test_export_gate_contract.py`: 22 tests, OK.
- `python -m unittest discover -s tests -p "test_*.py"`: 121 tests, OK — 2× consecutivas.
- `python scripts/validate_contracts.py knowledge/contracts`: exit 0.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/T10-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno.
