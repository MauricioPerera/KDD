---
type: 'Task Contract'
title: 'Planificar backlog relacionado del sprint'
description: 'Ordenar tareas elegibles explicando dependencias, ciclos, bloqueos y prioridad heredada.'
tags: ['sprints', 'backlog', 'ccdd', 'planner']
task: sprint-planner
intent: 'Obtener la siguiente tarea ejecutable y explicar impedimentos del backlog.'
target: src/sprint_planner.py
signature: 'def plan_sprint(data: dict) -> dict:'
test_command: 'python -m unittest tests.test_sprint_planner'
budget:
  cyclomatic_max: 15
  nesting_max: 3
tests: 'tests/test_sprint_planner.py'
tests_sha256: '06cb37922e387ac0a91036cdc80725e864f8b3c751920837e781112383ff8038'
touch_only: ['src/sprint_planner.py', 'src/sprint_graph.py']
deps_allowed: ['argparse', 'json', 'pathlib', 'collections', 'src.sprint_admission', 'src.sprint_graph']
forbids: ['network', 'subprocess']
---

# Planificador de backlog

## Intent
Implementar el [modelo de backlog](../data_models/sprint-backlog.md). La planificacion
precede a la admision y no reemplaza las garantias de los contratos ni el despachador.

## Interface
`plan_sprint(data: dict) -> dict`, pura, determinista, sin mutacion del snapshot.
CLI: `python -m src.sprint_planner archivo.json`; exit 0 con siguiente tarea,
1 sin ejecutables y snapshot valido, 2 con input invalido; siempre JSON salvo error de argumentos.

## Invariants
- Aplicar el modelo enlazado para schema, referencias, evidencia, ciclos, prioridad y salida.
- Delegar seleccion/estado/budget a validate_admission existente sin modificarlo.
- Derivar tareas satisfechas, ignorando completed_tasks recibido del cliente.
- Ciclos afectan sus miembros y dependientes; no impiden tareas independientes.
- Explicar causas originales y condiciones/responsables de bloqueos manuales.
- Producir alternativas contra el mismo saldo, no un lote reservado.
- Desempates deterministas y caminos iterativos; probar cadena de 1100 tareas.
- Recalcular con cada snapshot nuevo; no mantener cache obsoleta ni ejecutar sondeos.

## Examples
- A low, B urgent depende de A: A ejecutable con prioridad efectiva urgent y fuente B.
- A bloqueada, B depende de A y C independiente: ejecutar C, explicar A como causa de B.
- A y B ciclicas: ambas no ejecutables; listar componente ciclico sin recursion infinita.

## Do / Don't
- DO: incluir pruebas adversariales, cambios de evidencia y CLI real.
- DON'T: modificar oraculos existentes, inventar consumo o persistir aprobaciones.

## Tests
Oraculo tests/test_sprint_planner.py escrito y sellado antes de implementar.

## Constraints
PARAR y reportar si exige iniciar agentes, modificar tablero, reservar presupuesto
concurrente o modificar tests congelados. Budget de complejidad declarativo sin Nivel 2.
