---
type: 'Task Contract'
title: 'Discovery de Pages con dependencias de despliegue en PR'
description: 'Exigir el discovery aislado en el PR nativo antes del preview de Pages.'
tags: ['ci', 'pages', 'integration']
task: pages-pr-deploy-ci
intent: 'Detectar dependencias ausentes del despliegue antes de fusionar.'
target: .github/workflows/validate.yml
language: yaml
signature: 'Validate Pages discovery with deployment dependencies'
test_command: 'python -m unittest tests.test_pages_pr_deploy_parity'
budget:
  cyclomatic_max: 1
  nesting_max: 1
tests: 'tests/test_pages_pr_deploy_parity.py'
tests_sha256: '0004a7f5e91f8d06f9d9714ab0a81a2a4482d3945ebd1acc3bf9018e0de725a9'
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['Python3.11', 'PyYAML', 'pip', 'GitHub Actions']
forbids: ['llm']
---

## Intent
Aplicar el [protocolo de paridad de discovery](../pages-pr-deploy-parity.md)
sin sustituir el [preview real en ambos sistemas](pages-pr-build.md).

## Interface
En el job validate de Ubuntu para PR nativo, antes del build de preview,
ejecutar el [CLI aislado](pages-pr-deploy-environment.md) con `--repo-root .`
y `--venv-dir` bajo `RUNNER_TEMP`. El error falla el job.

## Invariants
Mantener jobs, matriz Ubuntu/Windows, ambas pasadas, permisos y checks previos.
Sin `continue-on-error`, secretos, despliegue ni publicacion de artifacts de PR.
No modificar runtime confiable ni el workflow de despliegue.

## Examples
- PR nativo Ubuntu: discovery aislado ejecutado antes del preview.
- Dependencia que el despliegue no instala: job falla antes de la fusion.
- PR nativo Windows: conserva el preview real y las dos pasadas previas.

## Do / Don't
- DO: usar el interprete limpio y los instaladores del workflow de despliegue.
- DON'T: heredar paquetes del job para concluir PASS.

## Tests
`tests/test_pages_pr_deploy_parity.py` verifica el cableado y la integracion.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si se requiere cambiar
un oraculo anterior, runtime aprobado o proteccion remota.