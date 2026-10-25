---
type: 'Task Contract'
title: 'Comprobar workflows en los dos validate de CI'
description: 'Instalar el motor fijado y validar todos los workflows antes de los pasos costosos sin reducir la matriz ni la suite.'
tags: ['ci', 'workflows', 'integration']
task: workflow-syntax-ci
intent: 'Impedir fusionar un workflow malformado aun cuando su evento no ocurra en el PR.'
target: .github/workflows/validate.yml
language: yaml
signature: 'validate_all_workflows(validate, matrix.os)'
test_command: 'python -m unittest tests/test_workflow_syntax_ci.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_workflow_syntax_ci.py
tests_sha256: '3fc6fcd1d040809ed459f59b3e493b6cc9034221e305051f16911576f7e68148'
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['Python3.11', 'actionlint@1.7.12']
forbids: ['llm']
---

## Intent
Conectar el [validador](workflow-syntax.md) conforme al
[protocolo](../workflow-syntax-ci.md), complementando el
[build real de Pages](pages-pr-build.md).

## Interface
Install pinned workflow checker y Validate all GitHub Actions workflows,
shell python y run literal. Siguen al baseline aprobado, preceden a Node,
publisher, comandos de contratos y suites. Install llama al script con
cache RUNNER_TEMP/kdd-actionlint y ambos GITHUB_ENV/PATH; check usa el
binario exportado y --repo-root . sin lista fija ni condicion de evento.

## Invariants
Mantener cuatro jobs, dos matrices Ubuntu/Windows, Python3.11, Node24,
los 19 gates, referencias explicitas y dos comandos/entornos identicos de
suite. Sin paths filters, nuevos jobs, supresiones, permisos write, secrets,
continue-on-error ni modificaciones a otros workflows o protecciones.
Fallo de instalacion o lint falla validate antes de los pasos costosos.

## Examples
- Workflow de deploy no ejecutado en PR pero invalido: validate falla en ambos SO.
- Workflows validos: los dos pasos terminan y siguen gates, Board y suites2x.

## Do / Don't
- DO: validar todos los archivos presentes y usar cache solo para herramientas.
- DON'T: limitarse al diff ni omitir nuevos .yaml por una lista hardcodeada.

## Tests
tests/test_workflow_syntax_ci.py verifica orden/invariantes y ejecuta los
cuerpos Python reales de los dos pasos en fixtures Git con motor oficial.
El caso negativo contiene la regresion real de Pages en otro workflow.

## Constraints
Contratos/oraculos primero y baseline humano antes de modificar CI.
No autoriza publicar, fusionar ni tocar protecciones; cualquier excepcion
a trusted-pr-gate necesita aprobacion especifica.
PARAR y reportar si se requiere otro runtime, oraculo previo o proteccion remota.
