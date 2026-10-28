---
type: 'Task Contract'
title: 'OID canonico para cada aprobacion del registro externo'
description: 'Rechazar aliases hexadecimales moviles sin restringir los contextos candidatos de Git.'
tags: ['approval', 'git', 'integration']
task: approval-ref-identity
intent: 'Fijar baseline y calidad al objeto commit exacto revisado.'
target: scripts/approval_registry.py
language: python
signature: 'def resolve(repo_root, candidate_ref, registry_json, *, explicit_baseline=None, explicit_quality=None, require_quality=False):'
test_command: 'python -m unittest tests/test_approval_ref_identity.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_approval_ref_identity.py
tests_sha256: '7c3b14c78d665c50a89fac93d2188000caa38789b695f711531b4e2206df4d5a'
touch_only: ['scripts/approval_registry.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---
## Intent
Aplicar [identidad y modos](../audit-mutation-approval-ci.md) sin cambiar el registro.
## Interface
Conservar resolve, CLI y errores APPROVAL_*. Los campos aprobados normalizados
deben coincidir con el OID de un commit real. Contexto candidato puede ser HEAD.
## Invariants
No aceptar ramas hexadecimales de ninguna longitud ni tags/arboles como aprobacion.
Cubrir SHA-1/SHA-256, baseline_ref/quality_ref y registro/explicito; conservar
normalizacion, entradas no seleccionadas, limite y ausencia de efectos.
## Examples
- rama 64-hex en SHA-1 movida con JSON intacto: rechazo antes y despues.
- OID real 64-hex en SHA-256: seleccion de calidad y baseline correcta.
## Do / Don't
- DO usar commits y movimientos de ramas reales y el comparador de baselines.
- DON'T imponer SHA-1 ni inferir la aprobacion desde HEAD.
## Tests
El oraculo crea grafos propios con Git real; verifica errores, CLI y controles
positivos y negativos con ambas representaciones nativas.
## Constraints
PARAR y reportar si requiere elegir referencias, modificar runtime o protecciones.
La publicacion no autoriza una excepcion del guard que protege este selector.
