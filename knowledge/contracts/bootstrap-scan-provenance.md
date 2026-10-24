---
type: 'Task Contract'
title: 'Procedencia de evidencia al inicializar'
description: 'Evitar que muestras de scans se acrediten como evidencia de un proyecto nuevo.'
tags: ['quality', 'maintenance', 'verification']
task: bootstrap-scan-provenance
intent: 'Evitar que muestras de scans se acrediten como evidencia de un proyecto nuevo.'
target: scripts/init_project.py
language: python
signature: 'def init_project(repo_dir, apply, name, repository=None) -> dict:'
test_command: 'python -m unittest tests/test_bootstrap_scan_provenance.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_bootstrap_scan_provenance.py
tests_sha256: '6de9a4124facb53e189e00ab57dd9f9a1baac2164564c8ada55c7e33f385b624'
touch_only: ['scripts/init_project.py', 'scripts/bootstrap_project.py', 'scripts/optional_evidence.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Dry-run lista removed_example_evidence sin escribir; apply quita solo muestras conocidas. Informes propios se conservan; summary nunca acredita scanId example_.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- Copia original inicializada -> cero muestras como evidencia; optional SKIP.
- Informe propio en ruta conocida -> se conserva; muestra requerida -> FAIL.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tests/test_bootstrap_scan_provenance.py. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
