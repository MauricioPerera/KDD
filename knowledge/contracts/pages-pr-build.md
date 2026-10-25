---
type: 'Task Contract'
title: 'Build real de Pages en PR antes de fusionar'
description: 'Compilar y validar Pages en los PR nativos y cubrir el import de paquete sin alterar despliegue, matrices o suites.'
tags: ['ci', 'pages', 'integration']
task: pages-pr-build
intent: 'Detectar errores reales del publisher y de imports antes de fusionar.'
target: .github/workflows/validate.yml
language: yaml
signature: 'validate_pages_pull_request(validate, matrix.os)'
test_command: 'python -m unittest tests/test_pages_pr_ci.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_pages_pr_ci.py
tests_sha256: '3dda9d6023f296cf7883d59e9f9793e938804dba8ad184e6cd825cee11872089'
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['stdlib', 'Git', 'Node.js', '@rckflr/llms-skills@0.4.1']
forbids: ['llm']
---

## Intent
Aplicar la [frontera de PR](../pages-pr-validation.md) y conservar el
[build existente](pages-build.md) y la [raiz confiable](ci-trusted-execution.md).

## Interface
- En el job validate existente, pasos Install pinned Pages publisher for PR y
  Build and validate Pages for PR; shell bash. Ambos se ejecutan solo con
  github.event_name == 'pull_request', !inputs.reusable_execution y
  github.repository == 'MauricioPerera/KDD'.
- Instalacion: npm ci --prefix site --ignore-scripts --no-audit --no-fund.
- Build: python site/build.py --output
  "$RUNNER_TEMP/kdd-pages-pr-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT-$RUNNER_OS"
  --ci-run-url "$CI_RUN_URL". CI_RUN_URL se forma con github.server_url,
  github.repository y github.run_id, en el env de ese paso.
- Ambos pasos siguen al setup existente de Node24 y preceden a Run each
  contract's test_command. Los errores de instalacion/build/validacion fallan
  el job y evitan que el PR acredite PASS.

## Invariants
Cumplir el [protocolo](../pages-pr-validation.md). Se mantienen dos matrices,
cuatro jobs, Ubuntu/Windows y los dos comandos identicos de suite. Sin nuevos
permisos, secrets, environments, despliegues, subidas ni continue-on-error.
No usar hashFiles como condicion para omitir un build nativo incompleto.
El runtime confiable permanece intacto. La [extension de inventario](../pages-ci-inventory.md)
permite al despliegue descargar solo manifests del CI exitoso de main; no el
bundle candidato ni artifacts de otro intento. El build de PR es preview estricto.

## Examples
- PR nativo sano: dos builds reales, uno por SO; publisher y strict validate pasan.
- Import absoluto regresivo del dispatcher: el proceso nuevo de integracion
  falla y el build real falla antes de fusionar.
- Archivo de site faltante o publisher invalido: falla el paso; no se omite.
- Consumidor externo/reusable por defecto: no ejecuta los pasos nativos de Pages.

## Do / Don't
- DO: usar el lockfile y un destino ausente fuera del checkout.
- DON'T: cargar helpers desde scripts/ para ocultar un fallo de import de paquete.
- DON'T: desplegar ni reutilizar el artefacto candidato en el workflow de main.

## Tests
tests/test_pages_pr_ci.py combina invariantes del workflow con procesos reales
de paquete/CLI y gate real en fixtures aisladas, incluidos fallo de gate y cwd
ajeno. Los oraculos previos de Pages, CI y bootstrap se conservan.

## Constraints
Baseline humano explicito antes de implementar. PARAR y reportar si se requiere
alterar oraculos previos, referencias aprobadas o protecciones remotas.
El budget es declarativo; no se afirma sandbox ni Nivel2.
