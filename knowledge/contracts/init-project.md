---
type: 'Task Contract'
title: 'Inicializador de proyecto desde la plantilla'
description: 'Instancia la plantilla KDD en un proyecto real: elimina los artefactos de ejemplo del manifiesto, reescribe el index y preserva toda la infraestructura, con dry-run por default.'
tags: ['kdd', 'init', 'plantilla', 'tooling']

task: init-project
intent: "Instanciar la plantilla KDD en un proyecto real eliminando los ejemplos del manifiesto sin romper ningún gate."
target: scripts/init_project.py
signature: "def init_project(repo_dir: str, apply: bool, name: str) -> dict:"
test_command: "python -m unittest tests/test_init_project.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_init_project.py"
tests_sha256: "c94dd16dc7786d27d37c8215e0aa8f613fc681b6dbe9df55a3fab17a95a9591f"
touch_only: ['scripts/init_project.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: init-project

## Intent
Última milla del propósito de la plantilla: estrenarla en un proyecto real sin heredar los
ejemplos y sin romper la KB — los gates de [C03](./validate-okf.md) son la red que el init
debe dejar verde. Metodología: [metodologia-ejecucion](../metodologia-ejecucion.md).

## Interface
```python
def init_project(repo_dir: str, apply: bool, name: str) -> dict:
    """Plan/aplicación de la instanciación. Devuelve dict con: removed (lista de rutas
    del manifiesto), index_rewritten (bool), readme_renamed (bool), applied (bool).
    apply=False -> dry-run: calcula el plan sin tocar NADA. name=None/'' -> no renombra.
    Aborta con ValueError (sin tocar nada) si algún artefacto del manifiesto falta:
    la limpieza es todo-o-nada."""
```
CLI: `python scripts/init_project.py [--apply] [--name <proyecto>] [--repo-dir .]` —
dry-run por default listando el plan; exit 0 ok · 1 I/O · 2 manifiesto incompleto.

## Invariants
- MANIFIESTO explícito (constante en el script): src/hello.py, src/users.py,
  tests/test_sample.py, tests/test_users.py, knowledge/data_models/users_table.md,
  knowledge/architecture/overview.md, knowledge/contracts/sample_task.md,
  knowledge/contracts/validate-user-record.md. Nada fuera del manifiesto se elimina.
- index.md reescrito sin enlaces a nodos eliminados ni enlaces muertos; el resto de sus
  líneas se preserva.
- --name reemplaza SOLO el título H1 del README.
- Post-apply (en copia): validate_contracts exit 0, validate_okf exit 0 (sin huérfanos ni
  enlaces rotos), unittest discover verde con los tests de infra restantes.
- Intocables presentes post-apply: validadores, assemble_context.py + ccdd/context.json,
  export_gate_contract.py, .agents/ (reglas+skill), specs/, docs/, OKF-SPEC.md,
  metodologia-ejecucion.md, contratos de infra, CI.
- Determinista; stdlib puro; sin red; sin subprocess; escribe solo dentro de repo_dir.

## Examples
- Dry-run sobre la plantilla íntegra -> plan con los 8 artefactos del manifiesto, exit 0,
  árbol intacto (ningún archivo modificado).
- Apply sobre una copia -> los 8 eliminados, index sin enlaces muertos, 3 gates verdes.
- Copia con src/users.py borrado a mano -> exit 2 "manifiesto incompleto", nada tocado.

## Do / Don't
- DO: plan legible en el dry-run (una línea por acción).
- DO: todo-o-nada — validar el manifiesto completo ANTES de borrar el primer archivo.
- DON'T: heurísticas por tags o globs para decidir qué es ejemplo; red; subprocess en el
  target; tocar el repo real desde los tests (solo copias temporales).

## Tests
(Los tests están en `tests/test_init_project.py`: dry-run inocuo, apply exacto al
manifiesto, gates verdes post-apply en la copia, intocables presentes, --name solo título,
manifiesto incompleto aborta, exit codes CLI.)

## Constraints
- PARAR y reportar si... dejar los gates verdes post-init exigiera modificar un intocable
  (p. ej. un test de infra que dependa de un ejemplo) — eso es un hallazgo de
  acoplamiento a reportar, no a parchear en silencio.
