---
type: 'Task Contract'
title: 'Observacion parcial del post-init interrumpido'
description: 'Recuperar estados parciales de modulos del temporal privado despues de un timeout real.'
tags: ['ci', 'windows', 'bootstrap', 'performance']
task: postinit-timeout-observation
intent: 'Identificar los planes y resultados de modulos cuando no existe reporte final.'
target: scripts/postinit_timeout_observation.py
signature: 'python scripts/postinit_timeout_observation.py --temp-root PATH --project-root PROJECT'
test_command: 'python -m unittest tests.test_postinit_timeout_observation'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 4
tests: tests/test_postinit_timeout_observation.py
tests_sha256: 'b12826e4640659496f478e9766fd0e5c52915bd7affeacfaa979cb3a01836883'
oracle_files: ['tests/test_postinit_timeout_observation.py', 'scripts/run_test_suite.py', 'scripts/process_tree.py', 'scripts/init_post_apply_suite.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/postinit_timeout_observation.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

En dos intentos de [main](https://github.com/MauricioPerera/KDD/actions/runs/43225471386)
y dos del [PR 187](https://github.com/MauricioPerera/KDD/actions/runs/43248776087)
el timeout impidio publicar el perfil final. Conservar los planes y resultados
ya escritos permite identificar los modulos pendientes antes de optimizar.

## Interface

El CLI recibe el temporal privado de una sola invocacion y la ruta exacta
de la copia inicializada que le entrega el lanzador del ensayo aislado.
La copia es hija directa de ese temporal. Solo interesan los directorios
directos kdd-suite-* con planes cuyo start_dir sea PROJECT/tests. No se
adivina la identidad por el prefijo de una carpeta ni se requiere modificar
el fixture del contrato init-project para el ensayo.

El primer ensayo aislado preparara su propia copia del SHA medido con
init_project --apply y la misma exclusion de recursion del fixture. Dara
esa ruta al lanzador nativo y al colector. La duracion de ese ensayo es un
diagnostico de la suite inicializada. La medicion oficial conserva el
comando completo de init-project dentro de los contratos.
Emite un JSON con state y modules. State es partial cuando existe una
observacion util, not_found cuando falta, e inconclusive si es ambigua o
invalida. La salida diagnostica de estos tres estados usa exit 0.

Cada modulo de una observacion partial contiene index, name, phase, cases y
duration_seconds. Cases es el numero de IDs planificados. Phase es completed
cuando el resultado persistido es legible y coincide con el plan. Phase es
incomplete cuando existe el plan y falta el resultado. Esos archivos no
demuestran que un proceso siga vivo, que llegara a arrancar o que pasara.
Duration_seconds aproxima el intervalo de escritura entre plan y resultado
para completed. Para incomplete vale null. Los modulos se emiten por indice
y sin inventar estados para los que carecen de plan.

## Invariants

- No volver a ejecutar ninguna prueba ni modificar archivos. No acreditar
  cobertura, exito del CI ni ausencia de modulos con esta observacion.
- Usar los archivos regulares y acotados de una sola suite inicializada.
  No seguir enlaces, junctions ni archivos con varios enlaces. Rechazar
  resultados incompatibles, rutas externas, duplicados y archivos truncados.
- Leer como maximo 256 KiB por archivo y emitir solo indices, nombres
  de modulos de prueba, fases, conteos y duraciones. No emitir rutas,
  IDs de casos, mensajes de prueba ni el contenido original de los archivos.
- Una suite ajena con start_dir valido en otra copia no aporta datos, incluso
  si esta usa el prefijo del fixture de perfil. Dos suites aplicables dan
  inconclusive y lista vacia. Un intento sin planes aplicables da not_found y
  lista vacia.
- Conservar el limite de 600 s y el veredicto del comando original. Un futuro
  ensayo aislado puede registrar el SHA, intento y temporal del comando
  medido. La observacion carece de autoridad sobre los checks requeridos.
- Conservar Ubuntu, Windows, cobertura y dos pasadas generales. Este
  contrato no altera workflows, runtime confiable ni protecciones.

## Examples

- Timeout real con un resultado y dos planes sin resultado: se informa un
  completed y dos incomplete. Los modulos sin plan no se describen.
- Dos directorios de planes aplicables: inconclusive sin mezclar resultados.
- No queda ningun plan del post-init: not_found.

## Do / Don't

- DO conservar el fallo y la observacion como datos separados.
- DON'T publicar archivos arbitrarios ni tratar una observacion como PASS.

## Tests

En Windows, forzar un timeout con el lanzador real y el Job anidado desde
una copia con nombre temporal estandar, como el fixture de init. En Ubuntu,
ejecutar un worker real que completa y otro que se interrumpe en su propio
grupo, y comprobar que el PID se termino antes de observar. Comprobar la
ausencia de reporte final, lectura sin mutacion, colision entre suites,
modulos duplicados, un resultado con IDs ajenos, enlaces y limite de bytes.

## Constraints

PARAR y reportar si se necesita publicar el ensayo en un workflow remoto.
Presentar primero el diff exacto y sus permisos. No modificar el CI oficial.
