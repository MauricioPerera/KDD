---
type: 'Task Contract'
title: 'Concurrencia nativa Windows de seis workers para ambas suites'
description: 'Cambiar solo el default de las suites Windows de KDD conservando contratos, callers y evidencia real.'
tags: ['ci', 'windows', 'performance', 'integration']
task: ci-windows-suite-six
intent: 'Completar el objetivo temporal sin quitar pruebas ni aumentar jobs o timeouts.'
target: .github/workflows/validate.yml
language: yaml
signature: 'validate.env.KDD_SUITE_WORKERS(inputs, github.repository, matrix.os)'
test_command: 'python -m unittest tests/test_ci_windows_suite_profile.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_ci_windows_suite_profile.py
tests_sha256: '096544aa19b0e19fa22c81a34ae0bf3e0acebfc55a5231c338f631ef7b68f05e'
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---
## Intent
Aplicar la [extension de perfil](../ci-windows-suite-concurrency.md) y conservar
la [frontera de procesos](ci-suite-processes.md).
## Interface
Cambiar exclusivamente el default nativo de suite en Windows de cuatro a seis.
Inputs explicitos prevalecen. Ubuntu conserva cuatro; callers y otros repos uno.
Contratos conservan cuatro y bootstrap exclusivo con 600 s. La copia post-init usa el [perfil revisado](init-post-apply-profile.md). Dos pasos de suite identicos y consecutivos.
## Invariants
Conservar cuatro jobs, nombres, matriz, permisos, pins, SDK, Board, inventarios,
casos, aserciones y skips historicos. No ampliar limites ni cambiar el runtime.
La API existente admite seis; cada modulo y sus fixtures siguen ejecutandose una
vez por pasada. Fallos reales siguen fallando y los inputs invalidos no ejecutan casos.
## Examples
- KDD nativo/Windows/sin input: suite seis y contratos cuatro.
- KDD Ubuntu: cuatro; caller reutilizable o repo ajeno: uno.
- Seis modulos reales sincronizados alcanzan la barrera y producen seis IDs exactos.
## Do / Don't
- DO verificar PIDs, barreras, fixtures, reportes frescos y una regresion genuina.
- DON'T contar un ensayo local como ahorro remoto ni ocultar la primera muestra lenta.
## Tests
El oraculo evalua el subconjunto de expresiones usado por el workflow y ejecuta
el runtime real extraido de Git en un bundle externo, con procesos y reportes reales.
Comprueba dos invocaciones, fallo genuino y copia inicializada sin .git, sin SKIP.
La integracion post-init retira tests/test_init_project.py para evitar recursion:
el oraculo debe seguir funcionando sin importar ese archivo. Una regresion real
inicializa una copia, elimina el helper y ejecuta el control de copia y sus diez
casos internos. Conserva todos los metodos y aserciones anteriores; no agrega SKIP.
## Constraints
PARAR y reportar si requiere otro baseline/runtime, proteccion o excepcion no revisados.
Revisar baseline antes de cambiar el workflow y autorizar nueva entrada externa/publicacion.
El objetivo remoto conserva dos intentos del mismo head y los limites originales.
