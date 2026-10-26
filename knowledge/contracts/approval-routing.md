---
type: 'Task Contract'
title: 'Aprobaciones aisladas en CI, guard y proyectos inicializados'
description: 'Conectar el selector externo conservando guard confiable, calidad obligatoria y las suites completas.'
tags: ['ci', 'bootstrap', 'integration']
task: approval-routing
intent: 'Usar referencias seleccionadas por contexto sin contaminar main ni otras propuestas.'
target: scripts/guard_pr_baseline.py
language: python
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests/test_approval_routing.py'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: tests/test_approval_routing.py
tests_sha256: '494c5ce45bc1dac55c20a03604a07646e6b0530af0023cb6fe96e2ac32cd2907'
touch_only: ['scripts/guard_pr_baseline.py', '.github/workflows/validate.yml', '.github/workflows/trusted-pr-gate.yml', 'scripts/init_project.py', 'scripts/bootstrap_project.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Integrar el [registro](../approval-registry.md) con el
[guard confiable](trusted-pr-gate.md) y la
[calidad del bootstrap](bootstrap-product-quality-ci.md).

## Interface
Agregar input approval_registry al workflow reutilizable y variable externa
KDD_APPROVAL_REGISTRY al modo nativo. El paso Select approved references
usa el selector antes del baseline, test_command, calidad y suites; escribe
KDD_APPROVED_BASELINE_REF y KDD_QUALITY_APPROVED_REF en GITHUB_ENV con valores
seleccionados. Inputs approved_baseline_ref/quality_approved_ref son modo
explicito; no se mezclan con registro ni se suplen con globals antiguos.
El CLI del guard admite --approval-registry como alternativa a --approved-ref,
y selecciona contra el merge propuesto leido de Git, nunca contra el checkout de main.

## Invariants
Conservar [protocolo y migracion](../approval-registry.md). El guard usa codigo
de main, permisos contents:read, sin checkout/ejecucion del PR. Proteger
scripts/approval_registry.py y su nombre importable. check(base,candidate,ref)
conserva API y controles existentes. Dos pasadas y matriz Ubuntu/Windows
permanecen; no agregar continue-on-error ni reducir checks.
El bootstrap API/CLI conserva quality/product.json obligatorio, usa quality_ref
seleccionado y rechaza ausencias antes de ejecutar oraculos de producto.

## Examples
- PR con baseline propio: guard y CI seleccionan la misma referencia.
- JSON malicioso agregado al PR: no reemplaza el registro externo.
- Proyecto nuevo: politica y checks reales pasan con sus refs; ref ausente falla.

## Do / Don't
- DO: conservar los modos explicitos para callers que ya seleccionan la referencia.
- DON'T: aprobar por editar el workflow, el selector o un JSON del candidato.

## Tests
tests/test_approval_routing.py usa un remoto bare local con refs/pull reales,
invoca el guard como proceso, prueba codigo candidato envenenado y ejecuta
la seleccion extraida del workflow y la calidad real de un proyecto inicializado.
Los tres casos que inicializan una copia se aplican a la plantilla integra.
En una copia ya inicializada declaran esa inaplicabilidad; una integracion real
verifica el inventario exacto de esos tres SKIP, sin errores de Git ni recursion.
Los otros seis casos siguen ejecutandose tambien en copias inicializadas.
Los controles sintacticos de todos los workflows permanecen vigentes.

## Constraints
PARAR y reportar si se necesita actualizar el baseline de oraculos, runtime
o protecciones. Las excepciones del guard requieren aprobacion especifica.
No debilitar la comprobacion de SHA, ascendencia o perimetro de calidad.
