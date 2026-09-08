---
type: 'Task Contract'
title: 'Admision de tareas al sprint'
description: 'Piloto determinista de seleccion, dependencias y presupuesto con interfaz JSON y CLI.'
tags: ['sprints', 'ccdd', 'pilot']
task: sprint-admission
intent: 'Rechazar tareas fuera de la seleccion, bloqueadas o sin presupuesto.'
target: src/sprint_admission.py
signature: 'def validate_admission(data: dict) -> dict:'
test_command: 'python -m unittest tests.test_sprint_admission'
budget:
  cyclomatic_max: 15
  nesting_max: 3
tests: 'tests/test_sprint_admission.py'
tests_sha256: '81983d18bcce4c7ee070105fdccde2b56fa016b1ce81e73e20f51ffaeb2ad816'
touch_only: ['src/sprint_admission.py']
deps_allowed: ['argparse', 'json', 'pathlib']
forbids: ['network', 'subprocess']
---

# Admision al sprint

## Intent
Aplicar un subconjunto del [protocolo](../sprints.md) como prueba ejecutable.
La funcion decide sobre un snapshot proporcionado; no ejecuta tareas ni reserva
presupuesto y no sustituye la validacion de contratos o la aprobacion integrada.

## Interface
`validate_admission(data: dict) -> dict` devuelve `admitted: bool` y `reasons: list[str]`.
CLI: `python -m src.sprint_admission archivo.json`. JSON en stdout, exit 0 admitida,
1 rechazada por reglas, 2 entrada invalida/no legible. Funcion pura; IO solo en CLI.

## Invariants
- Entrada con `sprint` y `request`, ambos objetos. Sprint: `status`, `selected_tasks`,
  `completed_tasks`, `budget`. Request: `task_id`, `dependencies`, `estimated_cost`, `phase`.
- Estados conocidos: draft, active, paused, closed, cancelled; solo active admite.
- Listas de IDs unicos no vacios; dependencias propias invalidas. No se asume que una
  tarea seleccionada este completada. Dependencias externas pueden estar en completed_tasks.
- Budget: `unit` string no vacio, `limit`, `consumed`, `verification_reserve` enteros
  no negativos; reserva <= limite. Coste entero no negativo en la misma unidad del budget.
  Bool, null, floats y campos ausentes son invalidos. Campos extra se ignoran.
- Phase: implementation o verification. Reserva posterior = reserva para implementation;
  max(0, reserva - coste) para verification. Admitir presupuesto si consumido + coste
  + reserva posterior <= limite. La reserva incluye toda verificacion pendiente y el
  bloque verification consume parte de ella; quien prepara el snapshot debe estimarla.
- Acumular rechazos en orden: SPRINT_NOT_ACTIVE, TASK_NOT_SELECTED,
  DEPENDENCIES_PENDING, BUDGET_EXCEEDED. Estructura invalida devuelve solo INVALID_INPUT.
- No mutar input ni consultar red, reloj, procesos o estado global. Snapshot y estimaciones
  son datos confiados del coordinador; no prueban ejecucion real, frescura o autoridad.

## Examples
- active, tarea seleccionada, dependencia completa, 60 + coste 20 + reserva 20 <= 100: admitida.
- Mismo snapshot, coste 21: BUDGET_EXCEEDED.
- 80 consumidos, verification 20, reserva 20, limite 100: admitida sin doble reserva.

## Do / Don't
- DO: fallar cerrado ante entrada incompleta y ofrecer CLI comprobada por los tests.
- DON'T: modificar el oraculo, introducir persistencia, integrar el tablero o afirmar ahorro.

## Tests
`tests/test_sprint_admission.py`: oraculo escrito antes del implementador y sellado.
Incluye fronteras, entradas malformadas, determinismo, no mutacion y CLI real.

## Constraints
PARAR y reportar si el alcance exige ejecutar agentes, escribir presupuesto compartido
o modificar reglas del tablero. La complejidad declarada no esta medida por Nivel 2.
