---
type: 'Task Contract'
title: 'Preparacion real de fixtures sin procesos redundantes'
description: 'Reducir arranques de PowerShell y configuraciones repetidas conservando Git y enlaces nativos reales.'
tags: ['ci', 'windows', 'integration', 'performance']
task: fixture-preparation-cost
intent: 'Preparar los mismos repos y enlaces con menos procesos y medir el efecto neto en CI.'
target: tests/test_fixture_preparation.py
language: python
signature: 'def directory_alias(link, target, owner):'
test_command: 'python -m unittest tests/test_fixture_preparation.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 160
  params_max: 4
tests: tests/test_fixture_preparation.py
tests_sha256: 'f5db56ffa20e5933a31fdc2b359b2cb961e04bb7352eaa5562d2dd45c4d1e612'
touch_only: ['tests/test_fixture_preparation.py', 'tests/test_bootstrap_boundary.py', 'tests/test_task_committed_artifacts.py', 'tests/test_task_git.py', 'tests/test_generated_task_evidence.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---
## Intent
Aplicar las [metricas y limites de CI](../audit-mutation-approval-ci.md).
## Interface
Helper de oraculo: crear un alias nativo de directorio nuevo dentro de owner;
resultado normalizado returncode/stdout/stderr describe la operacion nativa,
sin fingir un subprocess. Errores reales fallan y no se convierten en PASS.
configure_git(root, values): escribir configuracion local de un repo nuevo
de fixture; Git real la lee y ejecuta los commits. Solo claves/valores cerrados
de identidad, autocrlf, firma y mantenimiento sin detach ya existentes.
## Invariants
Windows usa junction nativa; Ubuntu symlink nativo. Cero procesos auxiliares.
Conservar canarios, permisos y paths Unicode/espacios; rechazar destino existente,
target ausente/externo y owner invalido antes de escribir. Cerrar handles.
La configuracion de fixture no inicia procesos config y conserva claves locales,
identidad, mantenimiento activo/sin detach e indice/HEAD. No cambia globals.
Los cuatro oraculos conservan todos sus metodos y aserciones. Sin mocks de
filesystem/Git, skips nuevos, cambios de limites, suites, workers o workflows.
## Examples
- junction real: lstat muestra reparse point y readlink resuelve al target propio.
- alias rechazado: no toca un archivo existente ni el canario externo.
## Do / Don't
- DO medir el mismo lote y dos intentos completos de CI del mismo head.
- DON'T presentar una reduccion local como ahorro probado del CI total.
## Tests
El helper y el oraculo se congelan juntos. Integraciones reales observan tipo de
objeto, rechazo y ausencia de subprocess, incluyendo los dos llamadores previos.
## Constraints
PARAR y reportar si requiere otro oraculo, runtime o proteccion no revisado.
El cierre de OP-3 exige la comparacion remota definida en la arquitectura.
