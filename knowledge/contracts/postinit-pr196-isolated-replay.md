---
type: 'Task Contract'
title: 'Reproduccion aislada del timeout de init del PR 196'
description: 'Ejecutar el comando completo sobre el arbol observado y recuperar los archivos parciales del mismo ensayo.'
tags: ['ci', 'windows', 'bootstrap', 'observability']
task: postinit-pr196-isolated-replay
intent: 'Distinguir el coste del comando completo de init y comprobar hasta donde llego el post-init sin cambiar el objeto medido.'
target: .github/diagnostics/postinit_pr196_replay.py
signature: 'python -I .github/diagnostics/postinit_pr196_replay.py --source DIR --bundle DIR'
test_command: 'python -m unittest tests.test_postinit_pr196_replay'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 4
tests: tests/test_postinit_pr196_replay.py
tests_sha256: '1bee338abf527008b14fe7e64029316883061aa2297fff658dc76a5a814640ee'
oracle_files: ['tests/test_postinit_pr196_replay.py', 'tests/test_postinit_timeout_observation.py', 'tests/test_fixture_preparation.py']
touch_only: ['.github/diagnostics/postinit_pr196_replay.py', '.github/workflows/postinit-pr196-replay.yml']
deps_allowed: ['stdlib', 'Git', 'GitHub Actions']
forbids: ['llm']
---

## Intent

Los intentos [1](https://github.com/MauricioPerera/KDD/actions/runs/43789463592/attempts/1)
y [2](https://github.com/MauricioPerera/KDD/actions/runs/43789463592/attempts/2)
solo acreditan que el comando de init agoto 600 s. El
[colector](postinit-ci-progress.md) permite observar el progreso durante un
nuevo intento. El replay es una observacion independiente y conserva su propia
identidad. El resultado identifica costes y limites observados antes de
seleccionar un cambio de rendimiento.

## Interface

El workflow vive en la rama aislada `codex/postinit-pr196-replay`. Solo arranca
en push de esa rama en MauricioPerera/KDD con Windows nativo, permiso
`contents: read` y checkouts con credenciales no persistentes. Separa el
checkout del control del checkout medido. Usa Python 3.11, Git nativo, Node 24,
locks de contexto, workflow checker, Board, Pages y MCP del objeto medido.

El objeto medido esta fijado al merge de prueba
`088225c2ff241b773353825f45c9e63a57861173` y arbol
`71e569b721d4f7785c3b8159a8befcdc06eaceed`. El lanzador comprueba SHA,
arbol y limpieza antes de ejecutar. Usa el baseline
`47afa8d45e6139e4ce8939fd4e8f07d65f85f7cb` en los dos entornos de aprobacion
local del comando. Valida el bundle externo materializado desde el runtime
fijado `74d357f7099651b9b39dc8088f725183a672ec94`.

Ejecuta `python -m unittest tests/test_init_project.py` desde el objeto
medido con el ejecutor de comandos del bundle y timeout exterior de 600 s.
El comando exclusivo de la matriz empieza primero y este ensayo lo ejecuta
aislado. La duracion incluye preparacion de la copia y todo el comando.
El propio fixture inicia su suite nativa de diez procesos en Windows.
Activa la marca aprobada mediante `KDD_OBSERVE_POSTINIT=1`.
El entorno del subproceso atribuye el checkout medido a GITHUB_SHA y conserva
el SHA de control por separado, junto con el run e intento del replay. El
checkout medido y el marcador viven en ubicaciones separadas.

Ante timeout, ejecuta el colector del objeto medido antes de limpiar el
temporal. Se publica unicamente `RUNNER_TEMP/kdd-postinit-pr196-replay.json`.
El resumen versionado contiene `source_sha`, `source_tree`, `probe_sha`,
`run_id`, `run_attempt`, `runtime_sha`, `duration_seconds`, `outcome` y
`observation`. Outcome conserva las tres claves `ok`, `error`, `exit_code`
del ejecutor. Observation contiene el resumen acotado del colector en timeout
y null si el comando no agoto el limite. Si el colector no ofrece un resumen
valido en timeout, emitir `inconclusive` con modulos vacios. El proceso
devuelve 124 al agotar el limite, el codigo real en un fallo ordinario
con codigo, y 0 en exito.

La funcion `check_checkout(source, sha, tree)` permite comprobar Git real.
`replay(source, bundle, env, timeout=600)` permite probar el reloj y la
contencion con una muestra corta. La CLI carece de un override del timeout
y usa el comando completo, el SHA y el runtime fijos.

## Invariants

- Cualquier variante de un commit, arbol o checkout sucio se rechaza antes
  de lanzar el comando. El replay solo toca el temporal que crea el workflow.
- Limite 600 s en el comando exterior. Mantener el veredicto incluso si el
  observador falla. El reporte tiene salida exclusiva y <= 192 KiB.
- Conservar solo metadatos y el resumen tipado de modulos del colector.
  Quedan excluidos rutas, transcript, IDs de casos y variables del entorno.
  Distinguir una falta de planes de una prueba no ejecutada.
- Mantener la matriz Ubuntu/Windows, las dos pasadas, la cobertura en la
  primera y el inventario de CI. El replay es un workflow aislado de
  verificacion. No comparte los artefactos de aprobacion con el PR.
- Al completar el comando verificar que el perfil de post-init reporta
  los 2.374 casos de la copia original con diez procesos.

## Examples

- Un ejercicio corto agota su limite exterior y conserva un resultado y un
  plan pendiente. La salida es 124 y el resumen atribuye el run del ensayo.
- Un comando falla por asercion. Devuelve su codigo de fallo sin evidencias
  que correspondan al timeout.
- Candidatos diferentes o con cambios de disco se rechazan antes de copiar.

## Do / Don't

Usar el ejecutor y el colector reales. La muestra permite observar donde se
acumulan los intervalos de trabajo y que planes quedaron incompletos. No
atribuir causalidad de sistema operativo ni el trabajo previo a partir de un
archivo que el supervisor no llego a escribir.

## Tests

Usar Git y procesos reales para conservar el codigo de fallo, interrumpir un
descendiente y recuperar resultados parciales de la copia seleccionada.
Comprobar los metadatos, el rechazo de un checkout sucio y el alcance estatico
del workflow. El ensayo remoto conserva su propio resultado junto con los
dos timeouts originales.

## Constraints

La referencia de contratos y oraculos requiere revision antes de implementar.
El ensayo aislado se usa como evidencia antes de definir la correccion de
rendimiento. PARAR y reportar si se necesita cambiar runtime o protecciones.
