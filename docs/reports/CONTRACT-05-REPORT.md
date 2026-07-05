# CONTRACT-05 — Integración del gate CCDD nivel 2 real — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-05-gate-nivel-2.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Suite `unittest` | ✅ verde 2× (**96 tests**: 80 + 16 del exportador) | corridas PM idénticas |
| Validadores (contratos + OKF) | ✅ exit 0 (6 contratos, 11 nodos) | corrida PM |
| Export gate-nativo | ✅ 100 % ASCII, `<task>.gate.md` en raíz (gitignorado), rutas y `test_command` reescritos | corrida PM |
| **`lint_task_contract` (gate REAL)** | ✅ `ok: true, 0 errors` sobre el export | ejecutado por el orquestador vía MCP |
| **`run_integration_gate` (gate REAL)** | ✅ `verdict: PASS, stage: all` sobre el export limpio — métricas `cyclomatic: 1, nesting: 0, params: 1, length: 14` dentro del budget firmado | ejecutado por el orquestador vía MCP |

**El nivel 2 dejó de ser una promesa del README: hay un camino probado y repetible** —
`scripts/export_gate_contract.py` emite la variante gate-nativa de cualquier task contract
KDD y el gate real la certifica de punta a punta.

## Los 3 hallazgos del gate real (historia completa, para quien integre otro entorno)

La integración se hizo por sonda iterativa contra el gate real; cada veredicto FAIL fue
feedback textual para la corrección siguiente:

1. **Encoding** (sonda inicial): el contrato con acentos/em-dashes españoles → `INVALID`
   en lint; el mismo contrato en ASCII → `ok: true`. FIX: normalización ASCII total en el
   export (NFKD + tabla de mapeos tipográficos). Los contratos fuente conservan su español.
2. **Rutas** (1ª corrección): `target`/`tests` con `../` → `tc-tests-frozen` ERROR (el
   gate no acepta rutas que escapen del directorio del contrato). FIX: el export se emite
   en la **raíz del repo** (`<task>.gate.md`, gitignorado vía `*.gate.md`) con rutas hacia
   abajo.
3. **cwd de ejecución** (2ª corrección): `run_integration_gate` corre los tests con
   **cwd = directorio del target** → `FAIL gate1-tests`. FIX: el export reescribe
   `test_command` a `python <relpath desde el dir del target>` (p. ej.
   `python ../tests/test_users.py`); los archivos de tests del repo son auto-ejecutables.
   El fix se probó a mano sobre el artefacto ANTES de re-delegar (PASS) y luego se
   verificó sobre el export limpio regenerado por el script (PASS).

Dos re-delegaciones quirúrgicas (dentro de la política de máx 2), cada una con el JSON
exacto del veredicto del gate como feedback.

## Entregado (`518549b` spec+contrato · `c6f8e63` implementación)

- `scripts/export_gate_contract.py` (stdlib, determinista byte a byte) + 16 tests.
- `.gitignore`: `*.gate.md`. README (nivel 2, EN/ES) y `.agents/AGENTS.md` (regla 4):
  el gate real se corre sobre el export.
- Task contract: `knowledge/contracts/export-gate-contract.md`. Evidencia de tarea:
  `.agents/logs/export-gate-contract-REPORT.md` (local).

## Verificación final del PM

Suite 2× (96/96), validadores, export regenerado desde cero y **ambas tools del gate real
ejecutadas por el orquestador** con los resultados de la tabla. La función de C04 quedó
además medida por el gate: complejidad ciclomática 1 — el implementador efímero de C04
entregó bajo el budget con margen 10×.

## Pendientes / ítems de seguimiento

Ninguno. Los 5 contratos de KDD están cerrados; el nivel 2 es operativo donde el MCP
`ccdd-complexity` esté disponible, y el nivel 1 sigue siendo suficiente donde no.
