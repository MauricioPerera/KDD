---
type: 'Task Contract'
title: 'Preparacion aislada de tareas iniciadas en fixtures de perimetro'
description: 'Evitar repeticiones de setup manteniendo repositorios, oraculos y evidencias reales.'
tags: ['ci', 'fixtures', 'git', 'performance']
task: postinit-perimeter-setup
intent: 'Reducir el costo de setup repetido de los casos de perimetro e historial.'
target: tests/test_task_finish_perimeter.py
signature: 'class PerimeterCase(unittest.TestCase):'
test_command: 'python -m unittest tests.test_postinit_perimeter_setup'
test_runner: python-unittest
budget:
  cyclomatic_max: 40
  nesting_max: 8
tests: tests/test_postinit_perimeter_setup.py
tests_sha256: '883b5519bc88ff6694fae33e1c6d61ff4899b0811ab5a97c0d031faf1c92f553'
oracle_files: ['tests/test_postinit_perimeter_setup.py', 'tests/test_generated_task_evidence.py', 'tests/test_fixture_preparation.py']
touch_only: ['tests/test_task_finish_perimeter.py']
deps_allowed: ['stdlib', 'test_generated_task_evidence', 'test_fixture_preparation', 'git']
forbids: ['network', 'llm']
---

## Intent
Reducir preparaciones repetidas detectadas en el post-init de Windows sin
omitir pruebas de perimetro ni modificar la politica de timeouts.

## Interface
Conservar `PerimeterCase`, `PerimeterProject` y todos sus llamadores. Preparar
una tarea sintetica iniciada por clase y proceso mediante los comandos reales,
y entregar un repositorio Git independiente por cada caso.

## Invariants
- La base inicial no contiene resultados de test ni evidencias generadas; cada
  cierre ejecuta su oraculo real y crea evidencia exclusiva en su clon.
- Los clones conservan configuracion, commits, ramas y branch_base correctos;
  modificar o cerrar una tarea no cambia otro clon ni la base.
- No compartir fuentes mutables entre procesos, ejecutar red ni usar mocks de Git.
- Conservar los metodos, aserciones, casos, dos pasadas, matriz y timeouts previos.
  El ciclo create/ready/start sigue ejecutandose en otras pruebas independientes.
- No declarar resuelto el timeout sin repetir el post-init real y el CI del head.

## Examples
- Dos casos ejecutan create/ready/start una vez en la preparacion y cierran por
  separado tareas reales con dos oraculos y dos evidencias independientes.
- Un fallo de preparacion falla explicitamente; nunca reutilizar un fallo o exito.

## Do / Don't
- DO medir Git y subprocess reales y comprobar clones y evidencias aislados.
- DON'T compartir resultados, omitir aserciones o ampliar los limites de tiempo.

## Tests
El oraculo nuevo inspecciona dos clones, llamadas reales y sus cierres. Los
oraculos y contratos anteriores deben conservar sus metodos y aserciones.

## Constraints
PARAR y reportar si se necesita modificar otro oraculo, runtime o proteccion sin
la revision expresa exigida por `knowledge/quality-approval.md`.
