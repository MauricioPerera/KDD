---
type: 'Task Contract'
title: 'Conservar Git directo seleccionado en Windows'
description: 'Impedir que la preparacion de validaciones vuelva al lanzador cuando PATH ya selecciona Git directo de la misma instalacion.'
tags: ['ci', 'windows', 'performance', 'integration']
task: validation-native-git-path
intent: 'Preservar la seleccion de Git nativo sin procesos ni cambios globales.'
target: scripts/validation_runtime.py
signature: 'def runtime_environment(environ=None, platform=None):'
test_command: 'python -m unittest tests.test_validation_native_git_path'
test_runner: python-unittest
budget:
  cyclomatic_max: 16
  nesting_max: 5
tests: tests/test_validation_native_git_path.py
tests_sha256: 'd8b58f76c619cfcdc3c72f3d608223706948f0a560007d964185b793ebcf4723'
touch_only: ['scripts/validation_runtime.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Preservar la optimizacion del workflow descrita en
[el protocolo de rendimiento](../postinit-windows-headroom.md).

## Interface
Conservar runtime_environment, prepare_runtime y CLI. En Windows, si el primer
Git que resuelve PATH es el ejecutable directo existente ucrt64/bin/git.exe o
mingw64/bin/git.exe de una instalacion con Git/cmd/git.exe, conservar ese PATH.
Admitir instalaciones portables, espacios, Unicode y comparacion de nombres
Windows sin distinguir mayusculas. No cambiar a otra instalacion.

## Invariants
- No iniciar procesos para preparar el entorno, ni cambiar el mapping recibido.
- Conservar el PATH ya seleccionado; prepare_runtime sigue siendo local al
  interprete y descendientes. Ninguna escritura a Git config, registro o shell.
- No buscar un Git posterior si un Git anterior gana la resolucion. Un PATH
  que selecciona MSYS u otro Git conserva el fallback historico a Git/cmd
  instalado en los roots existentes; si no existe, conservar el PATH.
- Sin ejecutable directo seleccionado, conservar el comportamiento anterior.
  Ubuntu permanece identico; CLI conserva argumentos y exit code del hijo.
- No agregar sondeos por llamada, caches persistentes ni dependencias externas.

## Examples
- CI elige Git/ucrt64/bin y runtime lo conserva; layout mingw64 tambien.
- Un Git anterior gana sobre el directorio directo posterior: no afirmar que
  se eligio el directo ni saltar la regla de fallback existente.
- Sin Git/cmd correspondiente: conservar el fallback anterior.

## Do / Don't
- DO ejecutar Git real y comprobar version, commits y ausencia de cambios ajenos.
- DON'T atribuir el microbenchmark al post-init ni modificar el workflow.

## Tests
El oraculo prueba ambos layouts, precedencia, casing, ausencia y fallback;
ejecuta un hijo real con Git y verifica el entorno y el codigo de salida.

## Constraints
PARAR y reportar si requiere otro archivo de produccion, runtime o proteccion.
Conservar los oraculos historicos y sus aserciones sin modificaciones.
