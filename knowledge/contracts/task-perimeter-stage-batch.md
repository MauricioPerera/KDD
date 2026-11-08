---
type: 'Task Contract'
title: 'Agrupar las lecturas del perimetro dentro de su etapa'
description: 'Reducir consultas Git de la historia lineal sin perder cambios transitorios o de integracion.'
tags: ['tasks', 'git', 'performance', 'integration']
task: task-perimeter-stage-batch
intent: 'Reducir el coste del perimetro y actualizar sus prioridades medidas sin omitir validaciones.'
target: scripts/task_git.py
signature: 'def _perimeter_paths(root, context):'
test_command: 'python -m unittest tests.test_task_perimeter_stage_batch tests.test_task_proof_batches.ClosedTaskProofBudget'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 4
tests: tests/test_task_perimeter_stage_batch.py
tests_sha256: '9f0d091c942c78f5f554a065888814e3330a05cf9d6a943bad1e0924ef03679d'
oracle_files: ['tests/test_task_perimeter_stage_batch.py', 'tests/test_task_proof_batches.py', 'tests/test_task_history_read_cost.py', 'tests/test_traceability_model.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py', 'tools/ci/postinit-module-order.json']
deps_allowed: ['stdlib', 'task_model', 'task_evidence', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Continuar el [objetivo medido](../postinit-perimeter-batch.md) sin modificar
el comportamiento del [perimetro obligatorio](task-finish-perimeter.md).

## Interface
Conservar task_perimeter, _perimeter_paths y las interfaces publicas.
Con identidades canonicas ya verificadas, una implementacion lineal y una
integracion de dos padres reconocida usa como maximo dos procesos Git en
la etapa fria de _perimeter_paths: diez para los tres commits del fixture.
La auditoria completa existente usa como maximo 44 procesos, frente a 48.

## Invariants
- Incluir todos los cambios de cada commit propio, incluso los revertidos.
  Incluir los cambios agregados por la integracion y excluir cambios ajenos
  de main. No sustituir la historia por un diff de los endpoints.
- Un camino rapido solo acepta una forma de grafo demostrada por filas
  completas de commits y padres. Merge ambiguo, estructura no reconocida,
  entrada no canonica, protocolo incompleto o error conservan el recorrido
  serial original y sus rechazos. No inferir conjuntos vacios de datos parciales.
- Mantener SHA-1 y SHA-256, nombres Unicode, espacios, tabs y saltos de linea.
  Un formato que no pueda interpretarse de forma inequivoca usa el fallback.
- Respetar reemplazos Git al consultar y su recuperacion entre operaciones.
  No publicar prefijos de resultados ni almacenar rechazos. Conservar estado
  de refs, rama, indice, config y checkout al hacer consultas.
- Agrupar solo metadatos de historia y cambios solicitados dentro de esta
  etapa. No adelantar artefactos, contrato, oraculo o producto de otras etapas.
  No crear lectores persistentes ni caches de resultados de validacion.
- Conservar los 2.135 IDs previos, todos sus metodos y aserciones, el limite
  seguro anterior de 62, timeout 600, workers, Ubuntu/Windows y ambas suites.
  El unico ajuste del oraculo anterior reduce su techo de 48 a 44.
- El perfil de modulos sigue el [contrato existente](postinit-module-order.md):
  ordenar los mismos jobs completos a partir de mediciones, nunca seleccionar
  casos. La simulacion no acredita el criterio remoto.

## Examples
- Una ruta fuera de permiso agregada y revertida sigue en el conjunto real.
- Un archivo ajeno agregado solo en main no se atribuye a la tarea.
- Un archivo agregado durante el merge si pertenece al perimetro integrado.
- Una implementacion que contiene un merge ambiguo mantiene TASK_PERIMETER.

## Do / Don't
- DO medir procesos con Trace2 y Git real, conservando los fallos.
- DON'T omitir auditoria, reciclar un PASS ni relajar limites para acelerar.

## Tests
Tres integraciones nuevas cubren coste, union historica, cambios de integracion,
estado de Git y reemplazos. El caso completo ya existente se reutiliza con
techo 44; conserva su ID historico y todas sus demas aserciones.

## Constraints
PARAR y reportar si falta la revision del nuevo baseline o se requieren
otros oraculos, runtime, workflow, workers, timeouts o protecciones.
El cierre sigue exigiendo tres CI completos consecutivos del mismo SHA final
de main, cada post-init Windows estrictamente menor de 480 s.
