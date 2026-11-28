---
type: 'Task Contract'
title: 'Copia acotada del fixture de perfil ya inicializado'
description: 'Evitar copias completas repetidas del proyecto cuando los controles del perfil solo necesitan sus archivos propios.'
tags: ['performance', 'windows', 'bootstrap', 'integration']
task: postinit-initialized-profile-copy
intent: 'Reducir escrituras del fixture, conservando todas sus verificaciones y comandos reales.'
target: tests/test_ci_windows_suite_profile.py
signature: 'def copy_profile_source(destination):'
test_command: 'python -m unittest tests.test_postinit_initialized_profile_copy'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 3
  lines_max: 40
  params_max: 1
tests: tests/test_postinit_initialized_profile_copy.py
tests_sha256: '762f4917e9af5e25b20f8d469c279feb75627e583b728ac6adf411dda3720f90'
touch_only: ['tests/test_ci_windows_suite_profile.py']
deps_allowed: ['stdlib', 'scripts']
forbids: ['network', 'llm']
---

## Intent

Reducir las tres copias de archivos del control de proyecto ya inicializado
de [seis workers](ci-windows-suite-six.md). El trabajo bajo prueba es ejecutar
el perfil real con el helper de bootstrap presente o retirado.

## Interface

Conservar `copy_profile_source(destination)` y el fixture sin Git. Si el
origen contiene cualquier entrada del manifiesto de bootstrap, copiar la
plantilla con las exclusiones previas. Si ninguna existe, copiar el workflow
de validacion, los seis archivos del runtime, el lector del manifiesto con
su modulo de transacciones, el paquete y los dos archivos del fixture.
Copiar ademas el helper de init cuando este presente para que el caso de
recursion pueda retirarlo.

## Invariants

- Cada destino recibe sus propios archivos con los bytes del origen.
  No compartir archivos modificables ni resultados entre invocaciones.
- Un archivo requerido ausente en el origen se detecta al copiar.
- La ruta de plantilla completa sigue ejecutando `init-project --apply`.
  Una plantilla parcial conserva las entradas que existian. Una entrada rota
  usa el recorrido completo y mantiene su error.
- Los doce metodos, sus aserciones y los procesos internos del oraculo
  anterior se conservan. Los dos controles de copia ejecutan el mismo
  conjunto interno de diez pruebas con sus seis procesos reales.
- El post-init de Windows conserva diez workers, 600 s, Ubuntu y ambas
  pasadas generales. El objetivo sigue siendo tres CI consecutivos del
  mismo SHA de main con post-init Windows <480 s.

## Examples

- Proyecto inicializado con un canario en docs: copiar doce dependencias
  y el helper solo si existe. El canario queda fuera del destino.
- Plantilla con una entrada del manifiesto: conservar esa entrada y los
  archivos ordinarios de la plantilla en la copia.

## Do / Don't

- DO ejecutar el mismo control desde un proyecto inicializado realmente.
- DON'T guardar un resultado de otro caso ni omitir los procesos internos.

## Tests

Las pruebas de copia comprueban bytes, independencia, manifiesto parcial,
exclusiones, entrada rota y fallo por dependencia ausente. El oraculo anterior sigue
ejecutando los procesos reales, sus dos invocaciones, el caso de fallo y la
copia sin Git desde una plantilla y desde un proyecto inicializado.

## Constraints

PARAR y reportar si falta la revision del baseline y de los sellos afectados.
Medir el comando completo antes de atribuirle al cambio un ahorro de CI.
