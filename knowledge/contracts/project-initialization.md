---
type: 'Task Contract'
title: 'Integracion real del arranque de un proyecto nuevo'
description: 'Corregir identidad del bootstrap y retiro de tareas heredadas, con un ciclo Git propio verificado sin mocks.'
tags: ['kdd', 'init', 'git', 'integration']
task: project-initialization
intent: 'Estrenar la plantilla mediante API o CLI sin identidad ni tareas heredadas de KDD.'
target: scripts/init_project.py
signature: 'def init_project(repo_dir: str, apply: bool, name: str, repository: str = None) -> dict:'
test_command: 'python -m unittest tests/test_project_initialization.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: 'tests/test_project_initialization.py'
tests_sha256: '768b06166a38397ebda976cb4a52f28490e1eef59cb11494f55c64773a6c1e8e'
touch_only: ['scripts/init_project.py', 'scripts/bootstrap_project.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess']
---

## Intent
Cumplir el [arranque guiado](./bootstrap-project.md) y la
[inicializacion](./init-project.md) con sus dependencias reales. El proyecto
nuevo debe poder usar el [diario de tareas](../git-tasks.md) sin el Git de KDD.

## Interface
Las interfaces publicas son las de los dos contratos enlazados. La CLI del
bootstrap acepta `--repository OWNER/REPO`; API y CLI producen la misma
politica de completion y conservan los perfiles existentes.

## Invariants
- Todas las escrituras y comandos Git de prueba ocurren en copias temporales.
- Bootstrap e inicializador, validadores, CLI de tareas y Git son reales.
- Dry-run no cambia archivos; errores de identidad o manifiesto no aplican
  limpieza ni escriben KDD-START-HERE.md.
- Apply retira TASK-001, TASK-002 y sus evidencias de demostracion. Archivos
  propios fuera del inventario se conservan byte a byte.
- Un Git nuevo inicia main sin tareas; contratos, OKF, specs, changelog,
  completion y snapshot de tareas pasan con la identidad del proyecto nuevo.
- Un contrato y oraculo propios permiten crear, aprobar, iniciar, integrar
  y cerrar TASK-001. El cierre ejecuta tests, versiona evidencia y el
  validador acepta todas las transiciones desde el primer commit propio.

## Examples
- API bootstrap con ExampleCo/Shop -> politica propia y guia standard.
- CLI bootstrap con perfil minimal -> guia sin SHA de aprobacion requerido.
- CLI init -> Git nuevo -> TASK-001 backlog, ready, in_progress y done.
- Apply sin repository o con manifiesto incompleto -> exit 2 y copia intacta.

## Do / Don't
- DO comprobar archivos, resultados de procesos e historial, no solo mocks.
- DO usar la referencia del oraculo creada en el fixture Git aislado.
- DON'T modificar refs, protecciones, aprobaciones ni tareas del repo real.

## Tests
El oraculo sellado tests/test_project_initialization.py cubre las rutas
publicas y los casos negativos con copias de la plantilla actual, sin
node_modules, .git ni archivos ignorados. En un proyecto ya inicializado
se omite esta suite de plantilla; no se omite en una plantilla integra.

## Constraints
- PARAR y reportar si hay que borrar archivos propios o falsear un PASS.
- La aprobacion Git del fixture es simulacion de un revisor para la prueba;
  no aprueba ni actualiza el baseline del repositorio KDD.
