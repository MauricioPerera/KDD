# CONTRACT-01 — Completar la plantilla KDD con la capa de ejecución y el ensamblador — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-01-completar-plantilla.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Validador de contratos | ✅ exit 0, 0 errores / 0 warnings (2 contratos) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**38 tests**: 17 baseline + 21 nuevos) | corridas PM idénticas |
| Ensamblador: aceptación | ✅ `assemble_context.py ccdd/context.json "documentar la tabla users"` → exit 0, retriever selecciona `users_table` | corrida PM |
| Determinismo | ✅ 2 invocaciones → stdout byte a byte idéntico (`cmp`) | corrida PM |
| `reference_check` | ✅ nodo citado inexistente → hallazgo reportado sin abortar | corrida PM |
| Forbids del target | ✅ sin `subprocess`/red en `scripts/assemble_context.py` | grep PM |
| CI | ✅ paso "Assemble context (smoke)" agregado; pasos existentes intactos | diff PM |

## Entregado

**E-SPECS + E-METODO** (`2562432`, autoría del orquestador): capa de contratos de ejecución
(`specs/` + `TEMPLATE-CONTRACT.md`; `docs/reports/` + `TEMPLATE-REPORT.md`), nodo OKF
`knowledge/metodologia-ejecucion.md` (type `Concept`, enlazado desde `index.md`), README
(EN/ES) con las piezas nuevas, y el task contract CCDD
`knowledge/contracts/assemble-context.md` (pasa el validador — la plantilla se aplica a sí
misma su propia metodología).

**E-ASSEMBLE** (`e1d6f58`, implementado por agente efímero contra el task contract):
`scripts/assemble_context.py` — ensamblador de contexto CCDD Nivel 2 en Python stdlib puro:
contrato JSON de slots (`ccdd/context.json`), presupuesto de tokens (1 tok ≈ 4 chars),
prioridades, compaction none/truncate/summarize, firmas sha256 12-hex, providers dinámicos
sobre la KB OKF (`okf_index`, `okf_nodes` con retriever determinista por mención de nombre
de nodo o tags del frontmatter, fallback a todos), guardrails `regex_deny` (abort → exit 2)
y `reference_check` (rutas `knowledge/*.md` citadas que no existen). 21 tests `unittest`.
Evidencia de tarea del agente: `.agents/logs/assemble-context-REPORT.md` (local, gitignorada,
según el ciclo de vida de KDD).

## Verificación final del PM (independiente del agente)

- `python scripts/validate_contracts.py knowledge/contracts` → exit 0.
- `python -m unittest discover -s tests -p "test_*.py"` → 38/38 OK, 2 corridas idénticas.
- Los 3 chequeos del CLI (aceptación, determinismo con `cmp`, reference_check) ejecutados
  directamente por el PM — salidas en la tabla de arriba.

## Pendientes / ítems de seguimiento

Ninguno. Posible siguiente contrato: usar el ensamblador como fuente de contexto estándar
en la delegación de tareas (referenciarlo desde `.agents/AGENTS.md`).
