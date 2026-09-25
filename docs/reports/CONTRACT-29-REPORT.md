# CONTRACT-29 — Herramienta de benchmark — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-29-benchmark-gates.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo (20) | ✅ verde sin modificarlo (sello `38ae21bc...`) | corrida PM |
| Ninguna aserción dispara subprocess/reloj real | ✅ `subprocess.run(`/`time.perf_counter(` solo dentro de `main` (verificado estructuralmente por el propio oráculo) | corrida PM |
| Mutaciones PM (fixtures propias, no las del dev) | ✅ warmup con exit code no-estándar capturado; `count_errors` sobre reporte mixto de 3 gates | corridas PM |
| Dogfood: corrida real contra el repo | ✅ 7 gates + suite 2×, exit 0, números consistentes con el benchmark ad-hoc previo (~0.04-0.09s/gate; suite 20.7s/11.8s) | corrida PM independiente |
| 7 gates | ✅ exit 0 (21 contratos, 37 nodos, 29 specs, 6 rule-sets, 6 skills, 29 changelog) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**394 tests**) | corridas PM |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

Formaliza el benchmark ad-hoc corrido a pedido del usuario tras v1.4.0 como herramienta
versionada, resolviendo honestamente la tensión central: un benchmark real necesita
`subprocess` + reloj de pared, lo opuesto al resto de la plantilla ("determinista, sin
subprocess"). La resolución es **inyección de dependencias**: `measure_repeated`,
`measure_suite`, `benchmark_gates`, `count_errors` y `format_report` son puras y reciben
`run_fn`/`timer_fn` OBLIGATORIOS (sin default) — el oráculo congelado siempre inyecta
fakes deterministas y jamás toca un proceso real ni el reloj. Solo `main` (sin inyección
explícita) construye las implementaciones reales — la única rama con efecto de lado, y
verificado ESTRUCTURALMENTE (vía `inspect.getsource`) que `subprocess.run(` y
`time.perf_counter(` no aparecen en ningún otro lugar del archivo.

**Decisiones honestas de alcance**: no es un 8º gate de CI (diagnóstico de
mantenimiento, no check de corrección — `.github/workflows/validate.yml` intacto);
ningún número de una corrida particular se documenta como verdad universal en
`knowledge/` o el README (dependen del hardware de quien la corre) — la baseline de
v1.4.0 ya vive en la memoria de sesión del usuario, no en el repo.

## Verificación final del PM (independiente del dev)

- Oráculo 20/20 con sello intacto; mutaciones con fixtures propias (no las del dev);
  dogfood real independiente contra el repo (7 gates + suite 2×, exit 0); 7 gates;
  suite 2× 394/394.
- Perímetro del dev limpio: SOLO `scripts/benchmark_gates.py`; sin re-delegaciones.
- Incidente de proceso propio: la entrada del CHANGELOG se agregó antes de crear el
  placeholder de este reporte, lo que hizo que `validate_changelog` (y por lo tanto la
  suite completa) marcara error transitorio durante la ventana de delegación — el dev
  lo reportó honestamente como "2 fallos preexistentes" en vez de tocarlo (fuera de su
  perímetro). Corregido por el PM creando el placeholder antes de la verificación final.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C29-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno.
