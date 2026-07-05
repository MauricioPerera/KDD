# Contrato 08 — Export cross-drive: fallo honesto

Prerrequisitos: C07 completado (HEAD `a1c8444`), suite 116 verde 2×, CI verde. Pendiente
documentado en `docs/reports/CONTRACT-07-REPORT.md`: `export_gate_contract.py` con
`--out-dir` en una unidad de Windows distinta a `--repo-root` muere con `ValueError` de
`os.path.relpath` ("path is on mount 'D:', start on mount 'C:'") etiquetado engañosamente
como "ERROR (contrato invalido)" y exit 2. Es preexistente a C07 (verificado contra HEAD
anterior) y lo detectó el PM al verificar T9.

> Capa: este es un **contrato de ejecución** (nivel proyecto). Las tareas que impliquen código
> delegado a un agente efímero llevan además su **task contract** CCDD en
> `knowledge/contracts/<task>.md` (validado por `scripts/validate_contracts.py`).

## EXPORT-XDRIVE (T10) — detectar el caso y fallar como I/O, no como contrato inválido

Los paths reescritos del export (target/tests relativos al export) no pueden cruzar unidades
en Windows — un relpath entre `C:` y `D:` no existe. Soportarlo exigiría rutas absolutas en
el export, que el gate real rechaza. La decisión de diseño es: NO se soporta; se falla claro.

FIX/OBJETIVO: antes de reescribir rutas, el export compara unidad (`splitdrive`) de
`--repo-root` y `--out-dir` resueltos; si difieren, falla con mensaje honesto de I/O que
nombre ambas unidades y la limitación ("las rutas del export no pueden cruzar unidades"),
con el exit code de I/O del script (no el de contrato inválido). El chequeo vive en una
función pura testeable con paths literales (vía `ntpath`), de modo que los tests del caso
Windows corran también en el CI Linux. En POSIX no hay unidades → chequeo no-op. Task
contract `export-gate-contract.md` documenta la limitación y el fallo. Invariante: el flujo
same-drive no cambia en nada (mismo output byte a byte).

## Criterios de aceptación

- [ ] `python scripts/validate_contracts.py knowledge/contracts` exit 0 y
  `python -m unittest discover -s tests -p "test_*.py"` verde (UNA corrida).
- [ ] Test unitario (vía `ntpath`, corre en Linux) que fija: unidades distintas → error de
  I/O con mensaje que nombra ambas unidades; misma unidad → pasa.
- [ ] En este host Windows: export con `--out-dir` en `C:` y repo en `D:` → exit code de
  I/O y mensaje honesto (ya no "contrato invalido"); export same-drive → `cmp` idéntico
  al de antes del cambio.
- [ ] Final: suite completa 2× verde; CI verde.

## Restricciones

- Tocar SOLO: `scripts/export_gate_contract.py`, `tests/test_export_gate_contract.py`,
  `knowledge/contracts/export-gate-contract.md`.
- Sin dependencias nuevas (stdlib); sin red ni subprocess.
- NO commitear (el PM commitea por tarea verificada). Si algo no se puede sin romper otro
  criterio, PARAR y reportar.
