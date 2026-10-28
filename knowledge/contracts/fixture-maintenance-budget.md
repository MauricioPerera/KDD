---
type: 'Task Contract'
title: 'Mantenimiento acotado en repositorios efimeros de pruebas'
description: 'Evitar hijos automaticos de Git en dos fixtures conservando los controles reales de mantenimiento.'
tags: ['ci', 'performance', 'integration']
task: fixture-maintenance-budget
intent: 'Reducir procesos efimeros sin perder cobertura de Git ni de su limpieza.'
target: tests/test_fixture_preparation.py
language: python
signature: 'def configure_git(root, values, *, ephemeral=False):'
test_command: 'python -m unittest tests/test_fixture_maintenance_budget.py'
budget:
  cyclomatic_max: 16
  nesting_max: 5
  lines_max: 180
  params_max: 5
tests: tests/test_fixture_maintenance_budget.py
tests_sha256: '72488c6844ab19f2ed08c81eed7f9c5e553d8c2a115289c54bb4595f1c4c3de3'
touch_only: ['tests/test_fixture_preparation.py', 'tests/test_task_git.py', 'tests/test_generated_task_evidence.py', 'tests/test_ci_git_fixture_lifecycle.py', 'tests/test_existing_git_fixture_lifecycle.py']
deps_allowed: ['stdlib', 'git']
forbids: ['network', 'llm']
---
## Intent
Aplicar el [presupuesto y medicion](../task-quality-fixture-remediation.md).
## Interface
configure_git agrega ephemeral=False; Repository y TaskProject agregan
automatic_maintenance=False. Llamadas anteriores siguen siendo validas.
## Invariants
Solo escribir configuracion local de fixtures propios antes de su primer
commit. El modo efimero no inicia housekeeping automatico; el modo dedicado
lo conserva activo y sincronico. Preservar metodos, asserts, limpieza y limites.
## Examples
- Seis commits efimeros: seis procesos Git, cero hijos de mantenimiento.
- Modo dedicado: hijo real sin detach finaliza antes del padre y limpieza.
## Do / Don't
- DO observar Trace2 y los objetos reales de Git en ambos OS.
- DON'T extrapolar el microbenchmark al CI ni tocar globals/workflows/runtime.
## Tests
El oraculo nuevo conserva configuracion externa y canarios; verifica ambos
helpers, modo dedicado y compatibilidad de copia sin Git.
## Constraints
Los cinco archivos congelados requieren revision conjunta del baseline.
PARAR y reportar si requiere otro oraculo o cambios de runtime/protecciones.
