# Contrato 06 — `init_project`: instanciar la plantilla en un proyecto real

Prerrequisitos: Contratos 01-05 (96 tests, 3 gates en CI + nivel 2 operativo). La plantilla
sabe validarse pero no estrenarse: quien la clona hereda los ejemplos mezclados con la
infraestructura, y limpiarlos a mano rompe la KB (huérfanos, enlaces, suite) — exactamente
lo que los gates de C03 detectan. Este contrato agrega la última milla del propósito
declarado ("Use this repository as a Template").

> Capa: contrato de ejecución. La tarea lleva su task contract CCDD en
> `knowledge/contracts/init-project.md`.

## I-INIT (T1) — `scripts/init_project.py` + tests sobre copia temporal

1. **Manifiesto explícito** (constante documentada en el script; nada de heurísticas por
   tags): artefactos de ejemplo = `src/hello.py`, `src/users.py`, `tests/test_sample.py`,
   `tests/test_users.py`, `knowledge/data_models/users_table.md`,
   `knowledge/architecture/overview.md`, `knowledge/contracts/sample_task.md`,
   `knowledge/contracts/validate-user-record.md`.
2. CLI: `python scripts/init_project.py [--apply] [--name <proyecto>] [--repo-dir .]`.
   - Sin `--apply` (default seguro): **dry-run** — lista exactamente qué borraría y qué
     reescribiría, exit 0, no toca nada.
   - Con `--apply`: elimina los artefactos del manifiesto, **reescribe
     `knowledge/index.md`** quitando los enlaces a nodos eliminados (sin dejar enlaces
     muertos ni secciones-lista vacías rotas), y con `--name` reemplaza el título H1 del
     README por el nombre dado (solo el título; el resto del README queda).
   - Exit 0 ok · 1 I/O · 2 si algún artefacto del manifiesto no existe (repo inesperado —
     abortar sin tocar nada: o se limpia todo o nada).
3. **Intocables** (verificados por test): validadores (`validate_contracts.py`,
   `validate_okf.py`), `assemble_context.py` + `ccdd/context.json`,
   `export_gate_contract.py`, `.agents/` (reglas + skill), `specs/` y `docs/` (plantillas
   y reportes — el dogfood de C04 queda como tutorial), `knowledge/OKF-SPEC.md`,
   `knowledge/metodologia-ejecucion.md`, contratos de infra
   (`assemble-context.md`, `agents-context-rule.md`, `validate-okf.md`,
   `export-gate-contract.md`, `init-project.md`), CI, tests de infra.
4. **Tests** (`tests/test_init_project.py`, unittest; PUEDEN usar subprocess): sobre una
   **copia temporal** del repo (sin `.git`): (a) dry-run no modifica nada (comparación de
   árbol); (b) apply elimina exactamente el manifiesto y nada más; (c) post-apply los 3
   gates corren VERDES en la copia (`validate_contracts`, `validate_okf` — sin huérfanos
   ni enlaces rotos —, `unittest discover` con los tests de infra restantes); (d) cada
   intocable existe post-apply; (e) `--name` reescribe solo el título; (f) manifiesto
   incompleto (borrar un archivo antes) → exit 2 sin tocar nada; (g) exit codes CLI.
5. `ccdd/context.json` no cambia; si el retriever del ensamblador queda sin los nodos de
   ejemplo, su fallback (todos los nodos) ya lo cubre — no requiere cambios.

## Criterios de aceptación

- [ ] Suite `unittest` verde (96 + nuevos), 2× al cierre, EN EL REPO REAL (que no se
  inicializa — los tests trabajan solo sobre copias).
- [ ] Ambos validadores exit 0 en el repo real.
- [ ] Test (c) demuestra: post-init en la copia, los 3 gates verdes — la plantilla
  estrenada nace sana.
- [ ] Dry-run por default demostrado por test.
- [ ] Evidencia del ensamblador (regla 7) en el REPORT del agente.

## Restricciones

- Tocar SOLO: `scripts/init_project.py` (nuevo), `tests/test_init_project.py` (nuevo),
  README (1-2 líneas en "How to use" mencionando el init, EN/ES). NO tocar los ejemplos
  en el repo real, validadores, ensamblador, exportador, knowledge/, .agents/ (salvo
  REPORT), CI.
- Python stdlib puro en el target; sin red; sin subprocess en el target (los tests sí).
- NO commitear. Si algo no se puede sin romper otro criterio, PARAR y reportar.
