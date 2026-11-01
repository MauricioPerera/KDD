---
type: 'Task Contract'
title: 'Revision externa exacta de cambios de CI confiable'
description: 'Permitir solo cambios de raiz de confianza autorizados fuera del PR con identidad exacta.'
tags: ['ci', 'security', 'approval', 'integration']
task: trusted-ci-change-review
intent: 'Permitir evolucion revisada de archivos protegidos sin autoaprobacion del candidato.'
target: scripts/guard_pr_baseline.py
signature: 'def check(base_ref, candidate_ref, approved_ref, *, reviewed_changes=None):'
test_command: 'python -m unittest tests.test_trusted_change_review'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: tests/test_trusted_change_review.py
tests_sha256: '1593f0a9721183a1cb96d26e202fd1ac11141538ec52aa135bc9f29171306ae1'
touch_only: ['scripts/guard_pr_baseline.py', '.github/workflows/trusted-pr-gate.yml']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Aplicar el [protocolo de revision exacta](../audit-p1-p2-remediation.md)
sin reemplazar la [frontera existente](trusted-pr-gate.md).

## Interface
El guard acepta JSON externo opcional `reviewed_changes`; el workflow de base
lo recibe de `KDD_TRUSTED_CHANGE_REVIEW`, una variable administrada fuera del PR. La revision incluye
schema_version 1, base_commit, candidate_tree y files con path, before y after;
cada lado es null o un objeto mode/oid Git. La API devuelve hallazgos; la CLI
falla ante datos invalidos. Ausencia equivale a la politica estricta anterior.

## Invariants
- La revision identifica base y arbol candidato exactos, asi como el conjunto
  completo de rutas protegidas y sus modos y blobs antes/despues. Rechazar
  duplicados JSON, campos extra, entradas repetidas, aliases y OIDs invalidos.
- El guard usa solo el codigo de base y objetos Git; no ejecuta ni hace checkout
  del candidato. No aceptar revisiones provenientes del arbol del PR.
- La seleccion del baseline de contratos y oraculos sigue siendo independiente;
  un cambio de oraculo sin aprobar bloquea aun con revision de infraestructura.
- Archivo agregado, borrado, renombrado o con modo cambiado requiere su entrada
  exacta; cambios fuera de la lista bloquean. Sin revision, conservar todos los
  rechazos y tests actuales de archivos protegidos y nombres de imports.
- No cambiar permisos, checks, exclusiones de suite o protecciones remotas.
  La primera instalacion del nuevo guard requiere autorizacion independiente.

## Examples
- Base, arbol, lista y objetos coinciden con revision externa -> sin hallazgos.
- Modo, blob, arbol, base, ruta adicional o JSON duplicado -> rechazo.

## Do / Don't
- DO usar repositorios Git y blobs reales; verificar fallo cerrado.
- DON'T autenticar revisiones por un archivo del PR ni ejecutar su codigo.

## Tests
`tests/test_trusted_change_review.py` crea Git real y controles de autorizacion,
variaciones de modo y objeto, aprobacion ajena, JSON y deriva del oraculo.
Las pruebas selladas anteriores conservan su semantica sin revision externa.

## Constraints
PARAR y reportar si se necesita cambiar una proteccion remota o aprobar runtime.
La referencia de contratos/oraculos se revisa antes de implementar. Las
protecciones remotas y la primera instalacion exigen autorizacion especifica.
No se afirma autenticacion criptografica de la identidad del revisor.
