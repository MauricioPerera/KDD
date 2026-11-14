---
type: 'Task Contract'
title: 'Criterios de cierre fijados al SHA que ejecutó CI'
description: 'Impide acreditar criterios de proyecto nuevos o reescritos con una ejecución anterior.'
tags: ['ci', 'evidence', 'git']
task: completion-tested-criteria
intent: 'Vincular los criterios del cierre al contenido que existía en el commit ejecutado.'
target: scripts/verify_completion_runs.py
signature: 'def verify_project(root, context, token, policy_path, specs_dir):'
test_command: 'python -m unittest tests.test_goldfish_completion'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_goldfish_completion.py
tests_sha256: '7784e0f1ad66cc4b027d75ee3f9dda68e0741d49f832b755602a4502a5681f55'
oracle_files: ['tests/test_goldfish_completion.py', 'tests/test_validate_completion.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/verify_completion_runs.py', 'knowledge/verification-guarantees.md']
deps_allowed: ['stdlib', 'validate_completion']
forbids: ['llm']
---

## Intent

El [cierre por CI](verify-completion-runs.md) debe conservar los criterios
que existían cuando corrió la validación que se cita.

## Interface

Conservar `verify_project` y la CLI. Los criterios distintos o sin fuente Git
regular se rechazan con `CI_CRITERIA_DRIFT`. Un manifiesto local distinto del
Git seleccionado al verificar HEAD se rechaza con `CI_EVIDENCE`. El formato
de manifiesto v1 se conserva.

## Invariants

- Para cada cierre cuyo reporte o manifiesto se añade o cambia, comparar el
  bloque bajo `## Criterios de aceptación` del spec declarado en el SHA del
  run y el SHA candidato. Seleccionar por la pareja reporte/manifiesto y
  comprobarla una sola vez, también si el manifiesto ya existía. Usar blobs Git
  regulares sin reemplazos, y rechazar ausencia, ambigüedad o error de lectura.
  Los pares históricos exentos sin manifiesto conservan su política.
- Si solo se modifica un spec que pertenece a un cierre con manifiesto v1,
  volver a comparar sus criterios con el SHA citado; este caso no consulta
  Actions otra vez ni activa el perímetro del nuevo cierre. Un cierre aún sin
  reporte puede seguir en preparación. La selección del spec usa `specs_dir`.
- Leer el manifiesto del candidato desde Git, con la misma protección de
  blobs regulares y reemplazos. En una consulta de HEAD, rechazar cambios
  locales que difieran del manifiesto o spec Git. Si el checkout de Actions
  corresponde a un merge de PR, usar el SHA candidato explícito para acreditar
  los criterios independientemente de los bytes del checkout.
- Permitir finales de línea equivalentes y los cambios en la marca de los
  checkboxes. Conservar texto, IDs, continuación y orden del bloque. La
  validación estructural existente sigue exigiendo las marcas de cierre.
- Conservar la comprobación remota de identidad, éxito, workflow y ancestro,
  así como el perímetro actual del cierre. La atribución a pruebas concretas
  por criterio sigue siendo responsabilidad de la evidencia y su revisor.
  En el perímetro se comprueban las rutas de origen y destino de un renombre.

## Examples

- Marcar criterios existentes, añadir reporte y citar un run válido: PASS.
- Añadir un criterio, reescribir su continuación o aportar por primera vez el
  spec después del run: FAIL, aunque coincidan reporte, JSON y candidato.
- Publicar el reporte de un cierre con un manifiesto preexistente y una
  redacción de criterios distinta a la ejecutada: FAIL.

## Do / Don't

Comparar objetos del SHA citado con el candidato. Un fixture HTTP/API acredita
el verificador local y su tratamiento de la respuesta, con alcance simulado.

## Tests

El oráculo crea commits reales, ejecuta el camino `verify_project` y sustituye
únicamente la consulta de Actions por una respuesta con la identidad esperada.

## Constraints

PARAR y reportar si se requiere modificar los cierres históricos o el workflow
solo para atribuir estos resultados.
