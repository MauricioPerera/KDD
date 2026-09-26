# CONTRACT-NN — <título> — REPORT

Fecha: <YYYY-MM-DD>
Spec: `specs/CONTRACT-NN-<slug>.md`
CI: https://github.com/OWNER/REPO/actions/runs/12345

Los IDs, estados y textos de evidencia deben coincidir exactamente con
`CONTRACT-NN-EVIDENCE.json`. El enlace CI corresponde a un run ya terminado
y exitoso del commit de implementacion, anterior a este cierre.

## Resultado por criterio

| ID | Estado | Evidencia |
| --- | --- | --- |
| AC-1 | locally_verified | <registro de prueba> |
| AC-2 | locally_verified | <registro de prueba> |
| AC-3 | locally_verified | <registro de prueba> |
| CI-1 | verified_in_ci | https://github.com/OWNER/REPO/actions/runs/12345 |

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Validador de contratos | ✅/❌ | salida real |
| Suite `unittest` | ✅/❌ verde 2× (<N> tests) | corridas del PM sobre el estado final |
| <criterio del spec> | ✅/❌ | <comando + salida> |

## <Tarea 1> (commit `<hash>`)

<Qué se entregó, decisiones no obvias, desvíos aceptados con su justificación.>

## Verificación final del PM (independiente del dev)

- <comando>: <resultado real>
- Suite 2× consecutivas: <N>/<N> ambas, exit 0.
- Reportes de tarea del dev (evidencia local, gitignorada): `.agents/logs/<task>-REPORT.md`.

## Pendientes / ítems de seguimiento

<Lista honesta o "ninguno". Un flaky detectado = tarea futura, no se ignora.>
