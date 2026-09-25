# CONTRACT-18 — Gate de rule contracts — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-18-rules-gate.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del gate (17) | ✅ verde sin modificarlo (sello vigente `e96e7a5c...`, fortalecido y re-sellado por el PM durante la ejecución) | corrida PM |
| Gate sobre el ejemplo real | ✅ `OK: todos los rule contracts son conformes · Resumen: 0 error(es) en 1 archivo(s)`, exit 0 | corrida PM |
| Mutación: golden aflojado sin re-sellar | ✅ `GOLDEN_FROZEN` con ambos hashes | mutación del PM sobre copia |
| Mutación: familia con typo (`boundz`) | ✅ `FAMILIA` nombrándola | mutación del PM |
| **Mutación: divergencia con sello VÁLIDO** | ✅ `REPRO` nombrando el caso — el gate re-ejecuta el motor, no confía solo en el hash | mutación del PM (re-selló el golden a propósito) |
| Capa opcional | ✅ dir vacío/ausente → INFO + exit 0 (post-init verde) | corrida PM + `test_init_project` en suite |
| 4 validadores + lint + YAML | ✅ exit 0 | corrida PM |
| Suite `unittest` | ✅ verde 2× (**233 tests**) | corridas del PM sobre el estado final |
| CI | ✅ ambas patas en success, con el paso nuevo "Validate rule contracts" | run del push de cierre |

## Qué quedó (la vertiente se defiende sola)

`scripts/validate_rules.py`: gate determinista de rule contracts — estructura JSON,
familias conocidas (un typo es ERROR, no una regla ignorada), `golden: {path, sha256}`
obligatorio y sellado (LF-normalizado, mismo algoritmo que `tests_sha256`, se sella con el
`--hash` existente), golden bien formado, `code_only` con razón, y **reproducción**: el
motor declarativo re-ejecutado sobre cada caso del golden debe producir
`violations - code_only_miss`. Capa opcional para proyectos sin rule contracts. Paso de CI
dual-OS; ciclo de vida documentado en `rule-contract-spec.md`; línea del gate en
`validacion.md` y en el nivel 1 del README (EN/ES). El gate importa SOLO el motor — jamás
un validador de dominio (oráculos independientes, condición de aborto del spec).

## Historia de la tarea (1 re-delegación — la clase reporte-honesto, otra vez)

1. **Entrega 1**: API correcta, pero el CLI imprimía "INFO: ... does not exist or has no
   *.rules.json files" siempre que no había findings — incluso tras validar el ejemplo
   real. Confundía "nada que validar" con "todo válido" y omitía el resumen. Lo cazó la
   verificación adversarial del PM; el oráculo tenía el agujero simétrico (nunca asertaba
   la ausencia de INFO con archivos presentes).
2. **El PM fortaleció el oráculo primero** (aserciones: con archivos validados, sin INFO y
   con "Resumen: ... 1 archivo") y lo re-selló — el fix queda congelado contra regresión.
3. **Re-delegación 1/2** al mismo dev: helper de escaneo compartido API↔CLI (un solo
   criterio de "qué es un rule-set"), INFO solo sin archivos, resumen estilo
   `validate_okf` con conteos.

Nota de arnés del PM: la primera corrida de mutaciones falló por un desajuste
`/tmp` Git-Bash ↔ Python en Windows (falso rojo del arnés, no del gate); se rehízo con
rutas nativas y las 3 mutaciones cazaron su regla exacta.

## Verificación final del PM (independiente del dev)

- Oráculo 17/17; gate sobre `examples/rules` exit 0 con resumen honesto.
- 3 mutaciones adversariales sobre copia (arriba) — incluida la crítica: sello válido +
  semántica rota → `REPRO`.
- 4 validadores + lint exit 0; suite 2× consecutivas 233/233.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C18-REPORT.md`.

## Pendientes / ítems de seguimiento

Siguiente natural de la vertiente (no bloqueante): segundo dominio para probar generalidad
de las 7 familias (candidato directo: papers-please de game-protocol — control de
fronteras, misma forma que compliance de pagos).
