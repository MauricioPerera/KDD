---
type: 'Task Contract'
title: 'Inicializador de proyecto desde la plantilla'
description: 'Instancia KDD sin ejemplos ni historial de cierres ajeno; crea una politica de completion propia y conserva la infraestructura.'
tags: ['kdd', 'init', 'plantilla', 'tooling']

task: init-project
intent: "Instanciar KDD en un repositorio nuevo sin arrastrar ejemplos, specs/reportes historicos ni la identidad de completion de upstream."
target: scripts/init_project.py
signature: "def init_project(repo_dir: str, apply: bool, name: str, repository: str = None) -> dict:"
test_command: "python -m unittest tests/test_init_project.py"
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_init_project.py"
tests_sha256: "5125d126939696be8ab2add1fa5a97cc676aef53fd05cb062151e4f52530b9d3"
touch_only: ['scripts/init_project.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: init-project

## Intent
Última milla de la plantilla: estrenarla en un repositorio real sin ejemplos ni
historia de cierre ajena. El caso de campo documentado en
[validacion](../validacion.md) encontro que la politica heredada de KDD
bloqueaba CI con `POLICY_REPOSITORY`. Los gates de
[OKF](./validate-okf.md) y [completion](./completion-evidence.md) deben
quedar verdes despues de inicializar.

## Interface
```python
def init_project(repo_dir: str, apply: bool, name: str, repository: str = None) -> dict:
    """Plan/aplicación de la instanciación. Devuelve dict con: removed (lista de rutas
    del manifiesto), index_rewritten (bool), readme_renamed (bool), applied (bool).
    apply=False -> dry-run: calcula el plan sin tocar NADA. name=None/'' -> no renombra.
    apply=True exige repository OWNER/REPO. Aborta sin tocar nada si falta
    algun artefacto o la identidad es invalida: limpieza todo-o-nada."""
```
CLI: `python scripts/init_project.py [--apply --repository OWNER/REPO] [--name <proyecto>] [--repo-dir .]` —
dry-run por default; exit 0 ok · 1 I/O · 2 manifiesto/identidad incompletos.

## Invariants
- MANIFIESTO explicito (constante en el script): ejemplos de producto,
  los 33 pares historicos `specs/CONTRACT-NN-*` y
  `docs/reports/CONTRACT-NN-REPORT.md`, y reportes exclusivos de KDD.
  Los templates y validadores no se eliminan; nada fuera del manifiesto
  se borra.
- `completion-legacy.json` se reescribe con el OWNER/REPO declarado y
  `legacy_pairs: {}`. CI ya no hereda los 33 SKIP ni la identidad upstream.
- `CHANGELOG.md` inicia la historia propia del proyecto en v0.1.0.
- index.md reescrito sin enlaces a nodos eliminados ni enlaces muertos; el resto de sus
  líneas se preserva.
- --name reemplaza el titulo H1 del README; las menciones a la historia de
  releases se alinean con el changelog nuevo.
- Post-apply (en copia): validate_contracts, validate_okf, validate_specs,
  validate_changelog y validate_completion exit 0; este ultimo informa
  `PASS=0 FAIL=0 SKIP=0` hasta el primer cierre propio. La suite de
  infraestructura restante pasa.
- En CI, el `test_command` de este contrato ejecuta la integración post-apply
  completa una vez. Las dos pasadas posteriores de la suite omiten solo ese
  caso mediante `KDD_SKIP_INIT_POST_APPLY_SUITE=1`; el resto corre dos veces.
- Intocables presentes post-apply: validadores, assemble_context.py + ccdd/context.json,
  export_gate_contract.py, .agents/ (reglas+skill), templates de specs/reportes,
  OKF-SPEC.md, metodologia-ejecucion.md, contratos de infra, CI.
- Determinista; stdlib puro; sin red; sin subprocess; escribe solo dentro de repo_dir.

## Examples
- Dry-run sobre la plantilla integra -> plan explicito, exit 0,
  árbol intacto (ningún archivo modificado).
- Apply sobre una copia con `--repository ExampleCo/Shop` -> historia
  retirada, politica nueva, index sin enlaces muertos, gates verdes.
- Apply sin repositorio o con nombre malformado -> exit 2 sin efectos.
- Copia con src/users.py borrado a mano -> exit 2 "manifiesto incompleto", nada tocado.

## Do / Don't
- DO: plan legible en el dry-run (una línea por acción).
- DO: todo-o-nada — validar el manifiesto completo ANTES de borrar el primer archivo.
- DON'T: heuristicas por tags o globs para decidir que borrar; red; subprocess en el
  target; tocar el repo real desde los tests (solo copias temporales).

## Tests
(Los tests están en `tests/test_init_project.py`: dry-run inocuo, apply exacto al
manifiesto, gates verdes post-apply en la copia, intocables presentes, --name solo título,
manifiesto incompleto aborta, exit codes CLI.)

Migracion aprobada del fixture: la copia excluye solamente las dependencias locales
en `tools/kdd-board/node_modules`, conservando fuente y lockfile. El oraculo verifica
el alcance del filtro y preserva archivos testigo en ese directorio tanto en dry-run
como en apply. No se reducen las aserciones existentes ni se aumenta el timeout.

## Constraints
- PARAR y reportar si... dejar los gates verdes post-init exigiera modificar un intocable
  (p. ej. un test de infra que dependa de un ejemplo) — eso es un hallazgo de
  acoplamiento a reportar, no a parchear en silencio.
