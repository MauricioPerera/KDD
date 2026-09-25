# CONTRACT-11 — CI: matriz Windows y suite 2× — REPORT

Fecha: 2026-07-07
Spec: `specs/CONTRACT-11-ci-windows-suite2x.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| YAML parsea | ✅ | `yaml.safe_load` sin excepción (corrida PM) |
| Matriz + suite 2× declaradas | ✅ | `windows-latest` presente; `grep -c "unittest discover"` = 2; pasos existentes intactos (verificado por parseo estructural del PM) |
| Suite local Windows 2× | ✅ 148 tests OK, dos corridas idénticas | corridas del PM en el host Windows real |
| **CI verde en AMBAS patas** | ✅ `validate (ubuntu-latest)` success · `validate (windows-latest)` success | run `28900048227` sobre el push de cierre (`gh run view`) |

## CI-WIN-2X / T1 (commit `c245f48`)

`.github/workflows/validate.yml` con `strategy.matrix.os: [ubuntu-latest,
windows-latest]` y `runs-on` parametrizado; los pasos existentes quedaron idénticos en
comando y orden; el paso de suite se desdobló en "Run unit tests (1/2)" y "(2/2)" (la
regla anti-flaky de la metodología como gate, no como disciplina). El test win-only del
cross-drive (`test_cli_cross_drive_exit1_io_not_contract_invalid`, C08) ahora se ejecuta
en la pata Windows del CI; en Linux se sigue salteando limpio.

Motivación cerrada: el único bug post-release del repo fue Windows-only (C08) y el CI no
podía reproducirlo; ahora la clase entera queda cubierta por el runner.

## Verificación final del PM (independiente del dev)

- `python -c "import yaml; yaml.safe_load(...)"` → OK; matriz y steps verificados por
  estructura (no solo grep).
- Ambos jobs del run `28900048227` en success, verificado con `gh run view` tras el push.
- Suite 2× en host Windows local: 148/148 ambas, exit 0.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C11-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno.
