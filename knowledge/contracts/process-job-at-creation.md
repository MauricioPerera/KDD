---
type: 'Task Contract'
title: 'Creacion directa de procesos en el Job Object'
description: 'Eliminar el interprete intermedio en Windows compatible conservando la contencion.'
tags: ['ci', 'windows', 'processes', 'performance']
task: process-job-at-creation
intent: 'Reducir arranques del controlador de procesos de Windows.'
target: scripts/process_tree.py
language: python
signature: 'def run(argv, *, cwd, timeout, **kwargs):'
test_command: 'python -m unittest tests.test_process_job_at_creation'
test_runner: python-unittest
test_scope: infrastructure
budget:
  cyclomatic_max: 18
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_process_job_at_creation.py
tests_sha256: '2b779ab321148d3d9217478d61d8c5ed5115aead91763f0e845e3fbec5a5ea32'
oracle_files: ['tests/test_process_job_at_creation.py', 'tests/test_process_exit_barrier.py', 'tests/__init__.py']
touch_only: ['scripts/process_tree.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

Reducir la preparacion repetida del
[ejecutor de CI](ci-trusted-execution.md). La asignacion en la creacion
preserva la [contencion](process-tree-timeout.md) y la
[barrera de terminacion](process-exit-barrier.md).

## Interface

Conservar la API de run y su CompletedProcess. En el perfil Windows
compatible, crear el objetivo en su Job con un solo lanzamiento del
objetivo. Su padre directo debe ser quien llama a run, incluso bajo un
Job exterior. El perfil POSIX conserva su grupo y su ruta directa.

El limite interno `_start_windows_job_target(argv, *, cwd, job, options)`
crea el proceso mediante la API nativa con el Job de esa invocacion.
Usa el enlace Win32 del Job propio para que el oraculo pueda observar
la preparacion del atributo `JOB_LIST` y la creacion real.
Devuelve un proceso compatible con el manejo de E/S y espera de run.
Si Windows no admite `JOB_LIST`, se puede usar la barrera anterior
cuando el objetivo aun no se intento crear. En la configuracion del
atributo, `ERROR_NOT_SUPPORTED` autoriza esa ruta. Otro error de
configuracion o cualquier fallo al crear el proceso se propaga.

## Invariants

- La asignacion al Job propio ocurre en la creacion, antes de ejecutar
  codigo del comando. Conservar propiedades de la barrera, los plazos y
  el aislamiento de invocaciones concurrentes.
- Conservar argv sin shell, Unicode, cwd, entorno, stdin, stdout y
  stderr, tanto separados como redirigidos. Preservar exit codes y los
  errores de ejecutable ausente, timeout, contencion y limpieza.
- Si el sistema carece del atributo de creacion, conservar la barrera
  anterior solo tras comprobar que no se inicio el objetivo. Un fallo
  de permisos o contencion sigue siendo error. No repetir un objetivo
  que pudo iniciar ni ejecutar una variante sin contencion.
- Conservar todos los IDs, dos suites independientes, Ubuntu y
  Windows, cobertura en la primera y el
  [plazo comun de post-init](postinit-windows-common-deadline.md).

## Examples

- Un comando con stdin y salidas separadas conserva sus datos y salida
  43, tambien bajo un Job exterior.
- Un proceso vivo pertenece al Job exacto de su invocacion.
- Una llamada vecina conserva sus resultados durante la cancelacion.

## Do / Don't

Usar procesos reales y comprobar handles del Job propio. Conservar las
pruebas existentes de arbol, pipes, plazos y limpieza.

## Tests

El oraculo prueba E/S real, salida a archivo y stderr combinado.
En Windows compatible, observa la pertenencia al Job exacto al
retornar CreateProcessW, antes de que run pueda asignar por separado.
Repite la comprobacion bajo un Job exterior. Inyecta falta de
capacidad, denegacion y parametro invalido en `UpdateProcThreadAttribute`
para `JOB_LIST`. Comprueba que el retorno de `CreateProcessW` con el
mismo codigo de falta de capacidad bloquea el reintento, incluso si el
control ejecuto el objetivo. La ruta anterior deja una sola marca.
Dos llamadas reales concurrentes comprueban Jobs propios y el exito de
la vecina tras un timeout. En POSIX se observan los grupos elegidos y
la interfaz directa.
La [barrera](process-exit-barrier.md) conserva sus controles reales.

## Constraints

PARAR y reportar si falta el baseline revisado o se necesita otra
ruta protegida. El fichero es tambien dependencia de oraculos
congelados. Para el arbol implementado se requieren una
[referencia final de oraculos](../quality-approval.md),
la [revision exacta de la ruta protegida](trusted-ci-change-review.md)
y la referencia aprobada del
[runtime materializado](ci-trusted-execution.md), con su manifiesto
completo. Conservar los demas bytes del runtime de referencia.

Mantener gates, workflows y protecciones. Fijar antes de medir el
checkout y runtime de referencia. Comparar tres intentos completos
del mismo candidato con tres de la referencia. Registrar por intento
el SHA de checkout, el runtime efectivo, su manifiesto, los arranques
Git y Python, la cobertura de la primera pasada y cualquier fallo.
Medir desde el inicio del workflow hasta el check requerido, con ambos
productores Windows y la ventana de post-init. Comparar las duraciones
individuales y la mediana. El microbenchmark local mide solo una fase.
