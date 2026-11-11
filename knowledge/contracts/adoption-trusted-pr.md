---
type: 'Task Contract'
title: 'Validar PR del consumidor con una revisión independiente'
description: 'Ejecutar los oráculos aprobados sobre el candidato en un job sin privilegios de escritura.'
tags: ['adoption', 'ci', 'security']
task: adoption-trusted-pr
intent: 'Vincular la validación de PR del complemento a un baseline independiente del candidato.'
target: tools/kdd-adoption/kdd-validate.yml
language: yaml
signature: 'name: KDD validation'
test_command: 'python -m unittest tests/test_adoption_trusted_pr.py'
test_runner: python-unittest
oracle_files: ['tests/test_adoption_trusted_pr.py', 'tests/adoption_remediation_support.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt']
budget:
  cyclomatic_max: 16
  nesting_max: 3
tests: tests/test_adoption_trusted_pr.py
tests_sha256: 'd7ca1ae14904bf4aac82080b8671972a849c91355056b63565220ade55a98648'
touch_only: ['tools/kdd-adoption/kdd-validate.yml', 'tools/kdd-adoption/validate.py', 'tools/kdd-adoption/README.md']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Cerrar el falso verde de un oráculo resellado y habilitar un control de PR en
un [repositorio existente](reusable-kdd-adoption.md).

## Interface

El workflow conserva push y ejecución manual y agrega `pull_request` en
Ubuntu y Windows. Lee `KDD_ADOPTION_APPROVED_REF` de una variable del repositorio.
El paso de validación extrae el lanzador de ese commit a un temporal externo
y lo invoca como `python -I VALIDATE --repo-root REPO --approved-ref SHA`.
El lanzador local admite la misma referencia con `--approved-ref` o la variable.

## Invariants

- Un PR exige referencia completa, existente y ancestro del checkout de
  integración del evento. Un valor ausente, relativo o de otra línea falla.
  Se verifica el Git real sin objetos de reemplazo.
- Los tres archivos administrados y, si se configuró, el manifiesto de
  dependencias deben coincidir con los archivos regulares aprobados. El pin se
  obtiene del commit aprobado. La extracción no ejecuta el lanzador candidato.
- Antes de preparar el entorno o ejecutar tests, se comparan el conjunto de
  contratos inmediatos y todos sus oráculos inventariados con el baseline.
  Se reutiliza `validate_baseline.py` del validador fijado para cada contrato
  del conjunto exacto. Los subdirectorios conservan su selección independiente.
  Una sustitución simultánea de prueba y sello falla. Se comprueban nuevamente
  los archivos aprobados después de preparar el entorno.
- Los dos sistemas ejecutan dos pasadas independientes del runner gestionado
  `python-unittest`. El veredicto exige evidencia de ambos intentos y preserva
  `executed_tests` como conteo por pasada. La política de calidad conserva
  su referencia independiente y sus dos pasadas. Push/dispatch sin referencia
  de adopción siguen disponibles como piloto.
- El workflow usa `pull_request` sobre la integración del evento, permisos
  `contents: read`, checkout sin credenciales persistentes y sin pasar secretos.
  Se ejecuta en runners efímeros hospedados. La guía exige que la política
  externa de fusión proteja el origen del workflow, todos los workflows
  capaces de suplantar sus checks y las reglas de revisión. El código de
  producto se ejecuta como en CI; esta comprobación no constituye un sandbox.

## Examples

- Lanzador candidato con centinela → rechazo sin ejecutar el centinela.
- Regresión de producto con el oráculo aprobado → fallo del oráculo.
- Cambio simultáneo de oráculo y sello → rechazo antes de correr tests.

## Do / Don't

- DO probar el cuerpo del paso con Git y Python reales.
- DON'T ejecutar código candidato bajo `pull_request_target` ni presentar
  el piloto como protección de rama habilitada.

## Tests

Workflow generado y ejecución de su paso contra Git real: referencia ausente,
no ancestral y aprobada, pin y lanzador sustituidos, oráculo resellado y dos
pasadas de la misma suite. GitHub Actions se verifica posteriormente con un PR
de consumidor autorizado.

## Constraints

Las reglas remotas y sus referencias externas se configuran por separado.
Se conservan las plataformas y las dos pasadas oficiales de KDD.
PARAR y reportar si se necesita cambiar protecciones o publicar el consumidor.
