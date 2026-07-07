# CONTRACT-12 — `tests_sha256` obligatoria: todo oráculo queda congelado por máquina — REPORT

Fecha: 2026-07-07
Spec: `specs/CONTRACT-12-tests-sha256-obligatoria.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Validador de contratos sobre el repo | ✅ | `Resumen: 0 error(es), 0 warning(s) en 8 archivo(s)` (sin editar contratos: ya sellados por C10/T1) |
| Mutación (fixture sin sello) | ✅ exit 1, ERROR `FM_TESTS_FROZEN` cuyo mensaje nombra `--hash`; sellado con el helper → exit 0 | fixture propio del PM (copia de `sample_task.md` sin la clave) |
| Helper `--hash` | ✅ imprime 64 hex, exit 0; el hash impreso deja verde al fixture (camino de cálculo compartido verificado en uso real); archivo inexistente → exit 1 | corrida PM |
| Doc normativa | ✅ `tests_sha256` en `validacion.md` y en la skill (antes 0 menciones, RECON) | grep PM |
| Validadores specs + OKF + coherencia de agentes | ✅ exit 0 / OK | corrida PM |
| Suite `unittest` | ✅ verde 2× (**151 tests**: 148 + 3) | corridas del PM sobre el estado final |
| CI | ✅ ambas patas (`ubuntu-latest` y `windows-latest`) en success | run `28901237200` sobre el push de cierre |

## SHA-OBLIGATORIA / T1 (commit `4a151c9`)

`tests_sha256` pasa de recomendada (WARNING) a **requerida** (ERROR `FM_TESTS_FROZEN`);
el mensaje de clave ausente nombra el comando de sellado. Helper
`python scripts/validate_contracts.py --hash RUTA` imprime el sha256 normalizado (LF)
usando la MISMA función que la verificación (`_calculate_tests_hash` — un solo camino de
cálculo, decisión fijada en el spec). Fixtures sellados; el test "ausente = WARNING" se
invirtió a "ausente = ERROR". Doc normativa alineada: `knowledge/validacion.md` (nivel 1)
explica la clave, el sellado y el trade-off para proyectos ya instanciados
(WARNING→ERROR al actualizar el validador); la skill `kdd-okf-ccdd-hybrid` suma la clave
a sus CCDD Fields y al ejemplo de frontmatter.

Retoques de integración del PM sobre la entrega del dev (misma clase que en C10):
(1) el trade-off de proyectos instanciados faltaba en `validacion.md` — exigido por el
spec ("documentarlo, no ocultarlo"); (2) "recalculan el hash automáticamente" corregido a
"exige re-sellar" (nada recalcula solo — doctrina de honestidad de T8); (3) mensaje del
ERROR a ASCII ("Sellá" → "Sellar", convención del repo).

## Verificación final del PM (independiente del dev)

- Fixture propio sin sello → ERROR con mención de `--hash`, exit 1; sellado con la salida
  del helper → `0 error(es), 0 warning(s)`.
- `--hash` sobre archivo inexistente → exit 1.
- `validate_contracts` (8), `validate_specs` (12), `validate_okf` (15) → exit 0;
  `test_agents_rules` → OK (la skill conserva sus referencias fijadas).
- Suite completa 2× consecutivas: 151/151 ambas, exit 0.
- Ambos jobs del run `28901237200` en success (`gh run view`).
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C12-REPORT.md`.

## Pendientes / ítems de seguimiento

Observación de proceso (3ª ocurrencia en C10-C12): los devs efímeros introducen acentos
en mensajes de script pese a la instrucción ASCII explícita — candidato a check
determinista futuro (lint de ASCII sobre los literales de `scripts/*.py`), en vez de
seguir cazándolo por inspección del PM.
