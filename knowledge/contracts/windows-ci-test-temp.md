---
type: 'Task Contract'
title: 'Temporales privados del CI nativo Windows bajo RUNNER_TEMP'
description: 'Cambiar solo la ubicacion de temporales de prueba, sin quitar casos ni modificar lectores de Git.'
tags: ['ci', 'windows', 'performance', 'integration']
task: windows-ci-test-temp
intent: 'Medir el efecto de usar el almacenamiento temporal del runner para las mismas pruebas completas.'
target: .github/workflows/validate.yml
language: yaml
signature: 'prepare_native_windows_test_temp(validate, github.repository, matrix.os, inputs.reusable_execution)'
test_command: 'python -m unittest tests.test_windows_ci_test_temp'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_windows_ci_test_temp.py
tests_sha256: 'f48b6bf2e0bffe9d9144e66fc60492db27e37d85aab7c0e0df4515162b7ab5a3'
oracle_files: ['tests/test_windows_ci_test_temp.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['stdlib', 'git', 'Node24']
forbids: ['llm']
---

## Intent
Evaluar la [ubicacion de temporales](../windows-ci-test-temp.md), conservando
el [perfil Windows](ci-windows-suite-six.md) y el
[runtime confiable](ci-trusted-execution.md).

## Interface
Agregar un paso Prepare native Windows test temp despues del smoke SDK y antes
de Validate contracts. Solo se aplica a MauricioPerera/KDD nativo,
matrix.os=windows-latest y !inputs.reusable_execution. Shell python.
Crear un directorio nuevo por job bajo RUNNER_TEMP, sin letra de unidad fija,
y exportar TEMP, TMP y TMPDIR con la misma ruta mediante GITHUB_ENV.
Emitir KDD_WINDOWS_TEMP seguido de JSON con runner_temp y test_temp para
comprobar en CI la ubicacion efectiva; no sumar este dato como prueba de 480 s.

## Invariants
- RUNNER_TEMP debe existir, ser directorio y quedar fuera del checkout y de
  otros repositorios Git. Resolver aliases antes de decidir. Fallos Git que
  no correspondan a ausencia de repositorio no autorizan el directorio.
- Dos preparaciones crean directorios distintos; los hijos reales Python,
  Node y sus repositorios Git usan el temporal exportado. Conservar otras
  variables y lineas de GITHUB_ENV. No cambiar configuracion Git global.
- Si falla crear el temporal o escribir GITHUB_ENV, el paso falla. Limpiar
  solo el directorio vacio propio recien creado si falla abrir/escribir el
  archivo; no borrar RUNNER_TEMP ni sus archivos previos. No prometer rollback
  transaccional de escrituras parciales ante fallos arbitrarios de disco.
- Conservar matriz, jobs, nombres de checks, pins, permisos, SDK, Board,
  19 gates, Ubuntu 4, suite Windows 6, contratos 4, post-init Windows 8/Ubuntu 4,
  ambas pasadas, timeout 600 s y presupuesto Git 62. No introducir cache ni servicio.
- No modificar runtime, codigo de producto, otros workflows ni oraculos
  previos. No desactivar protecciones del sistema ni controles de seguridad.
- Conservar los 2110 IDs anteriores. El oraculo nuevo se ejecuta completo en
  la plantilla y en la copia inicializada sin .git, leyendo el bloque real
  heredado del workflow. No depende de ejemplos ni agrega SKIP. La falta del
  paso o un perfil incorrecto sigue fallando tambien en la copia inicializada.

## Examples
- RUNNER_TEMP externo: hijos Python/Node crean temporales bajo un hijo privado.
- Alias hacia el checkout o base dentro de otro Git: rechazo sin escribir env.
- GITHUB_ENV es un directorio: error real, sin borrar un archivo previo del job.

## Do / Don't
- DO medir el init completo en GitHub y conservar las muestras fallidas.
- DON'T inferir que otra ruta es mas rapida solo por existir o por su unidad.

## Tests
Tres integraciones ejecutan el bloque real del workflow y procesos Python,
Node y Git. Comprueban herencia, aislamiento, aliases y errores reales de I/O.
La ausencia actual del paso equivale a no preparar entorno y debe fallar por
asercion, no por un import inexistente ni una infraestructura simulada.

## Constraints
PARAR y reportar si falta revisar baseline y diff exacto del workflow antes
de implementar. La revision se limita al paso descrito; no autoriza fusion,
excepciones ni otro runtime. Conservar 55 entradas externas al registrar el
arbol final autorizado. Solo se cierra el objetivo con tres CI completos
consecutivos del mismo head e init Windows <480 s, no con esta hipotesis.
