---
type: 'Task Contract'
title: 'Auditoria del diff contra contrato aprobado'
description: 'Comprueba perimetro, dependencias nuevas y presupuesto del target Python, JavaScript, TypeScript, Go o Rust contra un baseline aprobado.'
tags: ['ccdd', 'diff', 'quality']
task: change-contract-audit
intent: 'Impedir que una implementacion se aparte del contrato aprobado sin dejar evidencia.'
target: scripts/validate_change_contract.py
signature: 'def audit_change(repo_root, contract_path, base_ref, head_ref) -> list:'
test_command: 'python -m unittest tests/test_validate_change_contract.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 300
  params_max: 5
tests: 'tests/test_validate_change_contract.py'
tests_sha256: 'b8e589c431a9f1e835fb51a32b2ad6b20c086ce25538e854ec2f3c7f41be93ab'
touch_only: ['scripts/validate_change_contract.py', 'scripts/change_contract_multilang.py', 'scripts/guard_pr_baseline.py', '.github/workflows/validate.yml', 'knowledge/validacion.md', 'CHANGELOG.md']
deps_allowed: ['stdlib']
forbids: ['llm', 'network']
---

## Intent

Unir el [gate de perimetro](./perimeter-gate.md) y el
[enforcement de budgets](./budget-enforcement.md) en una auditoria opt-in del
cambio real entre dos commits. El contrato y sus limites se leen del commit
base aprobado, no del candidato, para que este no se amplie su propio permiso.

## Interface

`audit_change(repo_root, contract_path, base_ref, head_ref)` devuelve findings
con `rule`, `path` y `msg`. Ambos refs deben ser SHA completos y el base debe
ser ancestro del candidato. El CLI acepta `--contract`, `--base-ref`,
`--head-ref` y `--repo-root`; exit 1 si hay hallazgos duros.

## Invariants

- El diff de Git aporta los archivos cambiados, incluidos los agregados y
  eliminados. `touch_only` se comprueba contra todos ellos; cambiar el oraculo
  produce `TESTS_TOUCHED`.
- La politica proviene del contrato en el commit base. Cambiar el contrato en
  el candidato no permite ensanchar `touch_only` ni `deps_allowed`.
- Si cambia un target Python, los imports externos nuevos deben figurar en
  `deps_allowed` por nombre raiz de import. Stdlib e imports locales se aceptan.
  Imports externos ya presentes en base se conservan durante la migracion.
- El target Python cambiado se mide con los topes de `budget` del base.
  JavaScript, TypeScript/TSX, Go y Rust usan el
  [adaptador multilenguaje](./change-contract-languages.md) para analizar el
  codigo del commit candidato y los manifiestos de dependencias. Un lenguaje
  sin adaptador produce `CHECK_UNSUPPORTED`.
- Un cambio al manifiesto asociado se audita aun si el archivo target no
  cambia. La ausencia o sintaxis invalida del manifiesto produce un finding
  duro; una dependencia nueva debe estar aprobada en el baseline.
- Solo el manifiesto efectivo mas cercano al target activa la auditoria por
  cambios de manifiesto. Si cambia esa seleccion por agregar o quitar un
  manifiesto anidado, se comparan las dependencias efectivas de ambos commits.
- Un parseo fallido, un manifiesto requerido ausente o una metrica opaca
  produce un finding duro en lugar de un PASS parcial.
- No se ejecuta codigo del candidato ni se consulta la red.
- El guard confiable en `main` protege este script para impedir que un PR
  sustituya el gate mientras intenta aprobar su propio diff.

## Examples

- Solo cambia el target Python dentro de `touch_only`, usando stdlib y bajo
  presupuesto -> PASS.
- Un archivo fuera de `touch_only`, el oraculo alterado o un nuevo import
  externo no declarado -> FAIL.
- El candidato modifica el contrato para permitir `*` pero el base no -> FAIL.

## Do / Don't

- DO: usar un baseline revisado e independiente como `base_ref`.
- DO: informar por separado la cobertura no soportada.
- DON'T: confiar en el contrato que viene del commit candidato.

## Tests

El oraculo sellado `tests/test_validate_change_contract.py` crea repositorios
Git temporales y cubre perimetro, dependencias, presupuesto, baseline e
incompatibilidad de lenguaje.

## Constraints

- Git local y los parsers fijados en `requirements-change-audit.txt`; no red
  durante la verificacion.
- PARAR y reportar si el SHA base no existe o no es ancestro del candidato.
- La integracion en CI es opt-in y exige contrato y baseline explicitos.
