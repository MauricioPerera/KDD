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
oracle_files: ['tests/test_adoption_trusted_pr.py', 'tests/adoption_remediation_support.py', 'tests/test_adopt_project.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt', 'scripts/validate_contracts.py', 'scripts/validate_okf.py', 'scripts/validate_test_commands.py', 'scripts/validate_baseline.py', 'scripts/verify_quality.py', 'scripts/oracle_execution.py', 'scripts/oracle_inventory.py', 'scripts/validation_runtime.py', 'scripts/process_tree.py', 'scripts/unittest_oracle_runner.py']
budget:
  cyclomatic_max: 16
  nesting_max: 3
tests: tests/test_adoption_trusted_pr.py
tests_sha256: 'ea9c22236a60203b3bc3b01c2162ef02c04e1b77db8bee0dfd89279b1572d63d'
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
  La extracción y los controles fijados se inician fuera del checkout, con
  rutas absolutas al consumidor y sin reemplazos de Git. Un ejecutable
  candidato en el directorio de trabajo no participa en la resolución de Git.
- Antes de preparar el entorno o ejecutar tests, se comparan el conjunto de
  contratos inmediatos y todos sus oráculos inventariados con el baseline.
  Se reutiliza `validate_baseline.py` del validador fijado para cada contrato
  del conjunto exacto. Los subdirectorios conservan su selección independiente.
  Una sustitución simultánea de prueba y sello falla. Se comprueban nuevamente
  los archivos aprobados después de preparar el entorno.
- La entrada aprobada exige `test_runner: python-unittest` e inventario
  explícito y no vacío para todos los contratos seleccionados. Un contrato
  histórico con comando libre falla antes de ejecutar ese comando.
- Los dos sistemas ejecutan dos pasadas independientes del runner gestionado
  `python-unittest`. El veredicto exige evidencia de ambos intentos y preserva
  `executed_tests` como conteo por pasada. La política de calidad conserva
  su referencia independiente y sus dos pasadas. Push/dispatch sin referencia
  de adopción siguen disponibles como piloto.
- El workflow usa `pull_request` sobre la integración del evento, permisos
  `contents: read`, checkout sin credenciales persistentes y sin pasar secretos.
  Se ejecuta en runners efímeros hospedados. Para exigir la identidad del
  workflow automáticamente, una ruleset de organización o empresa exige
  el workflow desde un repositorio y revisión protegidos. En repositorios
  con checks por nombre, se exige además revisión independiente de
  `.github/workflows/**` y las rutas de CODEOWNERS, invalidación de revisiones
  anteriores y prohibición de bypass a contribuyentes. El workflow candidato
  puede cambiar su propio resultado y un check por nombre no acredita su
  identidad. El producto se ejecuta como en CI, sin aislamiento de seguridad.

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
pasadas de la misma suite con dos identificadores de proceso escritos por el
oráculo. Un helper inventariado alterado y un comando histórico fallan sin
ejecutar su código. Un ejecutable Git señuelo en el checkout no interviene.
GitHub Actions se verifica posteriormente con un PR de consumidor autorizado.

## Constraints

Las reglas remotas y sus referencias externas se configuran por separado.
Se conservan las plataformas y las dos pasadas oficiales de KDD.
PARAR y reportar si se necesita cambiar protecciones o publicar el consumidor.
