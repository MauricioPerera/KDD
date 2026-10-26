---
type: 'Task Contract'
title: 'Selector externo de referencias aprobadas por arbol'
description: 'Resolver aprobaciones independientes para main y propuestas sin autoaprobar candidatos.'
tags: ['quality', 'ci', 'integration']
task: approval-registry
intent: 'Leer un registro externo y seleccionar referencias revisadas para el arbol Git exacto.'
target: scripts/approval_registry.py
language: python
signature: 'def resolve(repo_root, candidate_ref, registry_json, *, explicit_baseline=None, explicit_quality=None, require_quality=False):'
test_command: 'python -m unittest tests/test_approval_registry.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_approval_registry.py
tests_sha256: 'b63f648937aa4b50fddb1db60a28590a5a582612cde087f541ecee90f7ce5c1a'
touch_only: ['scripts/approval_registry.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [registro externo](../approval-registry.md) y conservar la
[aprobacion humana](../quality-approval.md). No modificar refs ni variables.

## Interface
resolve devuelve candidate_commit, candidate_tree, baseline_ref, quality_ref
y source (registry o explicit). quality_ref puede ser None si no es obligatorio.
candidate_ref puede ser HEAD/FETCH_HEAD como contexto Git, pero las referencias
aprobadas solo admiten SHA completos. ApprovalError hereda ValueError.
El CLI lee el JSON desde KDD_APPROVAL_REGISTRY, admite --repo-root,
--candidate-ref, --explicit-baseline, --explicit-quality y --require-quality;
imprime JSON en exito y error legible con exit 2 si no puede seleccionar.

## Invariants
Conservar el [protocolo](../approval-registry.md). No leer un registro del PR,
elegir HEAD como baseline por defecto, ejecutar codigo candidato, modificar
Git ni sobrescribir entradas. Exigir schema_version entero 1 y trees no vacio.
Rechazar duplicados/campos extra, SHA invalidos, refs que no sean commits,
arbol ausente, modos mezclados y calidad ausente cuando es obligatoria.
Solo resolver en Git las referencias de la entrada seleccionada; un registro
no seleccionado sintacticamente valido no requiere objetos locales.
Validar el limite de 48000 bytes antes de invocar Git. Errores con prefijo
APPROVAL_REQUIRED/JSON/SCHEMA/SHA/REF/UNKNOWN_TREE/AMBIGUOUS/QUALITY/LIMIT.

## Examples
- Main A y PR B/C mantienen tres entradas; seleccionar B no cambia A ni C.
- Merge M con arbol B: conserva baseline B aunque M tenga otro SHA de commit.
- Registro apunta B a baseline A: el comparador real rechaza los oraculos B.

## Do / Don't
- DO: consultar Git con argv y devolver el origen exacto de la referencia.
- DON'T: aceptar aliases aprobados, hacer fetch de red o usar una referencia global como fallback.

## Tests
tests/test_approval_registry.py usa commits, ramas y merges reales; compara
contra el validador de baselines real y comprueba entradas ambiguas, calidad,
ausencia de efectos, datos maliciosos y limite antes de arrancar Git.

## Constraints
PARAR y reportar si se necesita elegir un baseline, aprobar runtime o alterar
protecciones remotas. Este selector solo consume decisiones revisadas.
No modificar otros oraculos ni aceptar la ausencia de referencia como SKIP.
