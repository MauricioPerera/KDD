# CONTRACT-33 — Auditor de seals débiles — REPORT

Fecha: 2026-07-17
Spec: `specs/CONTRACT-33-seal-audit.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo (15) | ✅ verde sin modificarlo, sello `d9594ece...` intacto tras la implementación (re-hasheado por el PM) | corrida PM |
| Perímetro T1/T2 | ✅ código solo `scripts/audit_seals.py`; docs solo sus 3 archivos declarados | `git status` PM |
| Dogfood | ✅ `python scripts/audit_seals.py` sobre este repo → **0 findings / 31 auditados**, exit 0; `--strict` también exit 0 (repo limpio) | corrida PM |
| Preflight intacto | ✅ su oráculo (14) sigue verde y `preflight.py --contract seal-audit` → 3/3 exit 0 — el auditor NO entró en `GATE_SPECS`, como exigía el contrato | corridas PM |
| 11 gates de CI + attestation | ✅ réplica local exacta: 12/12 exit 0 | corridas PM |
| Suite `unittest` | ✅ verde 2× (**609 tests**, exit 0 ambas, +15 del oráculo nuevo) | corridas PM |
| Greps de docs | ✅ `audit_seals` en validacion/index/README; "11 gates" de Nivel 1 intacto | greps PM |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra

Cierra la mitad diferida del feedback externo del C32 (*"help catch weak test seals early"*)
con la tesis en el título: **el sello garantiza integridad, no fuerza**. Un oráculo vacío, sin
asserts reales o que jamás menciona al target pasa `validate_contracts` verde; el auditor
detecta esa AUSENCIA mecánica (6 reglas `WEAK_*`, `ast` puro, solo lectura, `forbids` con
`subprocess` incluido — más estricto que el preflight). La CALIDAD de un assert existente queda
explícitamente fuera: eso es mutation testing, y el contrato lo dice.

El hallazgo del RECON es el corazón del diseño: el prototipo contra el repo vivo (ANTES de
congelar el oráculo) marcó 2 contratos... que resultaron **falsos positivos legítimos** —
contratos de coherencia auto-referenciales (`target == tests`). La regla de omisión quedó
congelada en el oráculo y el baseline real es 0/31. Sin ese prototipo previo, la regla se habría
descubierto como un FAIL del dev o un dogfood rojo.

Advisory por diseño (frontera mecánico/juicio): sin `--strict` SIEMPRE exit 0; `--strict` es la
elección del equipo, no del tool.

## Trade-offs y notas

- T1 declaró un núcleo interno `_audit -> (auditable, findings)` del que delegan las dos
  funciones públicas — revisado por el PM en el diff puntual: es factorización para cumplir el
  budget (ciclomática ≤14), sin cambio de contrato.
- El spec nació diciendo "30 auditados" y el repo real dice 31: el 31º es el PROPIO contrato
  seal-audit, creado después de redactar el spec. Corregido por el PM con nota explícita — el
  auditor se audita a sí mismo, y pasa.
- Los REPORT de los devs quedan como evidencia local no versionada, consistente con
  `.agents/logs/`.
