---
type: 'Task Contract'
title: 'Progreso recuperable del post-init de Windows en CI'
description: 'Vincular evidencia parcial del post-init a su intento real y conservar el fallo del comando despues del timeout.'
tags: ['ci', 'windows', 'bootstrap', 'observability']
task: postinit-ci-progress
intent: 'Recuperar los planes y resultados persistidos del post-init al agotar el limite de init.'
target: scripts/postinit_timeout_observation.py
signature: 'python -I scripts/postinit_timeout_observation.py --ci-output'
test_command: 'python -m unittest tests.test_postinit_ci_progress tests.test_postinit_timeout_observation'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  params_max: 4
tests: tests/test_postinit_ci_progress.py
tests_sha256: 'b3f1cb26a5f81fd9cc302dba60ca2370c72c97762d8f55672f06e00d627b47ab'
oracle_files: ['tests/test_postinit_ci_progress.py', 'tests/test_postinit_timeout_observation.py', 'tests/test_postinit_command_timing.py', 'tests/test_init_project.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/run_test_suite.py', 'scripts/process_tree.py', 'scripts/init_post_apply_suite.py']
touch_only: ['scripts/postinit_timeout_observation.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib', 'GitHub Actions']
forbids: ['llm']
---

## Intent

Los tres intentos de [main tras el PR 195](https://github.com/MauricioPerera/KDD/actions/runs/43728301459)
agotaron los 600 s. El [tiempo de init](postinit-command-timing.md) preserva el
veredicto y el SHA. El detalle por modulo se forma al terminar el post-init.
Reutilizar el [lector del ensayo aislado anterior](https://github.com/MauricioPerera/KDD/blob/e3398a7fa2113f681415d758b396b3e1341af5b8/scripts/postinit_timeout_observation.py).

## Interface

En el paso de comandos de contratos, activar KDD_OBSERVE_POSTINIT=1 solo en
Windows nativo de MauricioPerera/KDD para push a refs/heads/main, con el
workflow_ref exacto del propio validate.yml en esa rama. Usar el
temporal privado que ya crea el workflow. El fixture completo de
[init-project](init-project.md) invoca mark_project(project) justo antes de
lanzar el post-init. Es el unico marcador de proyecto. Identifica un hijo
directo del temporal por nombre, junto con el run, intento y SHA. El campo project contiene ese nombre. Escritura
exclusiva. Ante un fallo de diagnostico, el fixture prosigue con la suite.

Mantener KDD_INIT_TIMING. El mismo paso expone la salida init_timed_out a
GitHub Actions, con true solo para timeout segun el recibo del runtime.
Cuando esa salida sea true en el mismo perfil nativo, ejecutar
`python -I scripts/postinit_timeout_observation.py --ci-output`. El
colector escribe kdd-postinit-progress.json bajo RUNNER_TEMP y GitHub
lo sube con nombre kdd-postinit-progress-RUN-INTENTO-windows-latest.
El comando de diagnostico se puede ejercitar localmente en los dos sistemas.

El resumen tiene schema_version=1, run_id, run_attempt, head_sha,
trusted_runtime_ref, platform, state y modules. Cada modulo lleva index,
name, phase, cases y duration_seconds. Phase es completed cuando existe
un resultado compatible con el plan, incluso si contiene fallos, e
incomplete cuando existe plan y falta resultado. La duracion aproxima el
intervalo entre escrituras; incomplete lleva null. La existencia de plan
no confirma arranque. La ausencia de plan no acredita ausencia de casos.
State es partial para una observacion util, not_found cuando falta
evidencia e inconclusive cuando los datos son invalidos o ambiguos.

El modo local anterior --temp-root DIR --project-root DIR conserva su
salida state/modules y su lectura de solo lectura.

## Invariants

- Conservar Ubuntu, Windows, dos pasadas, cobertura de la primera, limite
  600, veredictos, permisos, pins, runtime aprobado e inventario anterior.
  Sin rerun automatico ni autenticacion nueva. El resumen es diagnostico.
- La suite y su proyecto se identifican dentro del temporal privado
  externo al checkout. El lector rechaza alias, hardlinks, escapes, JSON
  truncados, fuentes combinadas y resultados con inventarios incompatibles.
  Rechazar marcadores de otro run, intento o SHA.
- Limitar cada archivo observado a 256 KiB y la observacion a 512
  modulos y cada identificador de modulo a 160 caracteres ASCII. El resumen
publicado ocupa como maximo 192 KiB. Los archivos de plan y resultado son datos sin autoridad
  para aprobar. Publicar solo metadatos e identificadores de modulo
  acotados, sin IDs de casos, rutas, variables, stdout o stderr.
- El artefacto es un archivo nuevo con salida fija. La recoleccion no
  cambia planes o resultados. El workflow sube un resumen cuando el
  colector lo produce, sin devolver exito al comando que agoto su tiempo.

## Examples

- Un worker termino con un fallo y otro tiene plan sin resultado. El
  recibo muestra completed e incomplete y el timeout permanece.
- El marcador falta. Publicar not_found con modules vacio.
- El marcador pertenece a otro intento o usa un enlace. Publicar
  inconclusive con modules vacio.

## Do / Don't

- DO ejecutar los controles con el retiro real de procesos.
- DON'T atribuir progreso a un PR distinto ni publicar datos del producto.

## Tests

Usar el lanzador y workers reales para interrumpir una suite con trabajo
acabado y pendiente. Verificar el artefacto acotado del intento y controles
de ausencia, alias, corrupcion, duplicidad y procedencia. Verificar las
condiciones exactas y la subida fijada del workflow. El fixture productivo
marca la copia antes de lanzar procesos y continua si la marca ya existe.
La adaptacion del control previo usa la ruta canonica del temporal en Windows.

## Constraints

La referencia de contratos y oraculos se aprueba antes de implementar.
PARAR y reportar si se necesita cambiar el runtime fijado o una proteccion remota.
La integracion del workflow sigue la revision de [cambios protegidos](trusted-ci-change-review.md).

En el [reparto nativo](ci-windows-board-routing.md) la fila Windows de
contratos conserva sus resultados sin ejecutar las suites o el verificador
de particiones. La fila de suites realiza ambos pasos de suite y la misma
verificacion de post-init. Los perfiles anteriores conservan sus criterios.
