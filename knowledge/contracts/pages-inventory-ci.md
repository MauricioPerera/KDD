---
type: 'Task Contract'
title: 'Transportar inventarios del run exacto entre CI y Pages'
description: 'Exportar despues de ambas suites, descargar ambos SO del evento y exigir discovery y evidencia completos antes de publicar.'
tags: ['ci', 'pages', 'workflow']
task: pages-inventory-ci
intent: 'Vincular la cifra publica al CI terminado del mismo commit conservando las matrices y las dos pasadas.'
target: .github/workflows/deploy-pages.yml
language: yaml
signature: 'validate_and_publish_pages_ci_inventory(workflow_run)'
test_command: 'python -m unittest tests/test_pages_inventory_ci.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_pages_inventory_ci.py
tests_sha256: 'fce30c8f825fd05b8dcf2b64ffb455d4be6fe5c1fc9e0bf59450e023363e373f'
touch_only: ['.github/workflows/deploy-pages.yml', '.github/workflows/validate.yml']
deps_allowed: ['GitHub Actions', 'Python3.11', 'Node24', 'Git']
forbids: ['llm']
---

## Intent
Conectar el [protocolo](../pages-ci-inventory.md) al
[build en PR](pages-pr-build.md) y al [build publico](pages-build.md).

## Interface
En los pasos compartidos de validate: Export Pages CI inventory y Upload Pages CI inventory, despues
de Run unit tests (2/2), solo push nativo de main. El export usa los reportes
reales y github.run_id/run_attempt/sha, matrix.os y KDD_TRUSTED_RUNTIME_REF.
En la [division nativa Windows](ci-windows-board-routing.md) los ejecuta
solo win_suite, con el mismo nombre de artefacto.
Pages agrega Install pinned discovery parsers, Download Ubuntu CI inventory
y Download Windows CI inventory antes de Build and validate public bundle.
Entre las descargas y el build, Resolve CI inventory runtime lee los dos
inventory.json con Python aislado y emite trusted_runtime_ref como salida
del paso ci-runtime. Exige dos valores hexadecimales completos en minuscula
e identicos, con un solo valor por clave en cada manifest. Ante falta,
ambiguedad, ruta insegura o desacuerdo falla sin emitir la referencia.
El build recibe ambos manifests, intento y el SHA explicito de esa salida.
La seleccion vive en el workflow de despliegue y conserva compatibilidad
con el build y los manifests v1 de un checkout historico.

## Invariants

Los inventarios de Pages siguen saliendo de las filas que ejecutan las
dos suites. La matriz auxiliar
[post-init Windows](postinit-windows-common-deadline.md) entrega evidencia
de bootstrap al mismo check obligatorio.
Cumplir [procedencia, pins y permisos](../pages-ci-inventory.md). Mantener
los jobs base, dos matrices Ubuntu/Windows, dos comandos identicos de suite,
Python3.11, Node24 y los 19 gates. Los seis archivos del runtime y
trusted-pr-gate conservan sus bytes. La activacion de un SHA de runtime
aprobado se verifica por separado. Pages toma la identidad del CI que
produjo los artifacts y prescinde de la variable de runtime vigente en el
despliegue. El build conserva la validacion completa de run, intento, SHA,
runtime, IDs, cuatro hashes distintos y discovery local.
Conservar protecciones y permisos, con despliegue solo del push aprobado.
El unico permiso nuevo en deploy es actions:read. Descargar manifests JSON,
nunca HTML, codigo ejecutable ni artifacts de otro run/intento.

## Examples
- Main exitoso con cuatro reportes exportados: build y despliegue coherentes.
- El CI termino con A y la variable apunta a B: desplegar la evidencia de A.
- Un artifact falta, expira o no valida su digest: abortar antes del build/upload.
- Dos artifacts del mismo run declaran runtimes distintos: abortar sin salida.
- Consumidor reusable o PR: no export/upload nativo; el PR conserva preview.

## Do / Don't
- DO: nombres exactos ligados al evento, dos destinos separados y SHA completo.
- DON'T: seleccionar run-id: latest, merge-multiple, patrones, permisos write
  o continue-on-error. Los nombres de SO ubuntu-latest/windows-latest son validos.

## Tests
tests/test_pages_inventory_ci.py comprueba cableado, procedencia, pins,
instalacion de parsers, argumentos del build y preservacion de la matriz.
La [integracion real](pages-inventory.md) ejecuta la seleccion del workflow
contra artifacts de Git real y cuatro pasadas. Comprueba rotacion,
consenso, ausencia de salida en errores y procedencia antes del bundle.

## Constraints
Baseline humano antes de implementar. No autoriza publicar, fusionar ni
cambiar protecciones. Los pins se revisaron en repositorios oficiales.
PARAR y reportar si se necesita otro permiso, runtime u oraculo fuera de
la propuesta revisada, o modificar una proteccion remota.
