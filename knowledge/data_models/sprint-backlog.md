---
type: 'Data Model'
title: 'Backlog relacionado y planificacion del sprint'
description: 'Snapshot de tareas, dependencias, evidencia, prioridades y bloqueos para planificar sin despachar.'
tags: ['sprints', 'backlog', 'dependencias', 'planificacion']
---

# Backlog relacionado

Formato opt-in del planificador. Aplica el [protocolo de sprints](../sprints.md) y
reutiliza la [admision](../contracts/sprint-admission.md) para seleccion y presupuesto.
Es un snapshot confiado del coordinador; no consulta archivos de evidencia ni ejecuta agentes.

## Entrada

Objeto JSON con `sprint` y `tasks`. Sprint conserva `status`, `selected_tasks` y `budget`
de admision. `completed_tasks`, si llega, se ignora: se deriva de las tareas y sus
prerrequisitos. Todos los IDs seleccionados y todas las dependencias deben existir.

Cada tarea requiere `id` no vacio, `status` (backlog, ready, in_progress, done,
cancelled), `priority` (low, medium, high, urgent), `dependencies` (IDs unicos),
`estimated_cost` (entero no negativo). Opcionales:

- `phase`: implementation por defecto, o verification; misma semantica de reserva de admision.
- `evidence`: null por defecto, o `{valid: bool, reference: string no vacio}`.
- `blockers`: lista vacia por defecto. Cada bloqueo requiere `id`, `reason`, `owner`,
  `condition` (strings no vacios), `status` (open o resolved). IDs unicos por tarea.
- `relations`: lista vacia por defecto de `{type, target}` sin pares duplicados.
  `related_to` y `duplicates` referencian tareas existentes; `goal` y `contract`
  contienen referencias externas no vacias. Son metadatos, no prerrequisitos.

Strings de ID/referencia sin espacios exteriores. Campos extra se ignoran para
compatibilidad. Campos requeridos ausentes, booleanos como costes, tipos incorrectos,
IDs duplicados o referencias a tareas inexistentes invalidan el snapshot completo.
Un bloqueo externo se representa con owner y condition; no como dependencia fantasma.

## Dependencias y evidencia

`A.dependencies = [B]` significa que A necesita B. Satisfecha exige done, evidencia
valid con referencia, ausencia de bloqueos open y TODOS sus prerrequisitos satisfechos.
Una evidencia invalidada propaga insatisfaccion incluso a sucesores marcados done.
La invalidez no cambia estados persistidos ni autoriza reejecutar una tarea done:
el coordinador debe revisar su evidencia o devolverla a ready.

Detectar componentes ciclicos, incluidos autorreferencias, con IDs ordenados; ciclos
no se presentan como orden topologico. Solo sus miembros y dependientes quedan
afectados; una tarea independiente puede seguir. Ciclos en relaciones informativas
no bloquean. Algoritmos iterativos para evitar limites de recursion en cadenas largas.

## Elegibilidad y prioridad

Elegible requiere ready, seleccion, sprint activo, cero bloqueos abiertos, cero ciclos
y dependencias satisfechas. Consultar admision con completed_tasks DERIVADO y coste
de la tarea. Una alta prioridad nunca evita un rechazo de admision.

Prioridad efectiva = maximo entre la propia y las prioridades de entregas seleccionadas
pendientes que dependen transitivamente de ella. No heredar de cancelled, satisfechas
o tareas fuera de seleccion, ni atravesar una dependencia ya satisfecha. Conservar
prioridad original, `priority_sources` que justifican un aumento y `unlocks` con las
entregas seleccionadas pendientes a las que contribuye. No seleccionar automaticamente
prerrequisitos externos al sprint.

Orden: prioridad efectiva descendente, cantidad de unlocks descendente, ID ascendente.
`executable` contiene alternativas admitidas contra EL MISMO saldo, no un lote reservado.
`next_task` propone solo la primera; despues de cada ejecucion hay que actualizar el
snapshot y planificar de nuevo. No hay concurrencia, reservas atomicas ni WIP automatico.

## Salida y reactivacion

Objeto con `valid`, `errors`, `cycles`, `executable`, `next_task` y `tasks` ordenadas por ID.
Error estructural: valid false, sin tareas ejecutables. Por tarea: `satisfied`, `eligible`,
`reasons`, `blocked_by` (prerrequisitos directos pendientes), `root_causes`, prioridades,
`unlocks`, `relations` y `recheck_on` (IDs de la tarea y prerrequisitos transitivos).

Root causes conserva origen y codigo; bloqueos manuales incluyen ID, motivo, owner y
condition. Un prerrequisito ready aun no completado se explica como DEPENDENCY_PENDING.
Si existe impedimento mas profundo se expone su origen, evitando llamar causa raiz
al mero intermediario. Propagar todas las causas distintas, deduplicadas y ordenadas.
Tambien se explican presupuesto, seleccion y estado que impiden ejecutar prerrequisitos.

recheck_on explica revalidacion de ELEGIBILIDAD: incluye dependencias satisfechas para
detectar evidencia invalidada. No es una lista completa de eventos de ordenacion:
un cambio de prioridad, dependencias o estado de un descendiente tambien puede cambiar
la prioridad heredada de su prerrequisito. El consumidor debe recalcular el plan completo
ante cualquier cambio del backlog, seleccion, estado del sprint o budget. No implementa
sondeo, suscripciones ni deteccion automatica de cambios: un consumidor invoca de nuevo.

CLI `python -m src.sprint_planner snapshot.json`: JSON en stdout; exit 0 si hay
next_task, exit 1 si snapshot valido sin tareas ejecutables (incluido todo terminado),
exit 2 si entrada invalida o ilegible. Ningun codigo equivale a aprobar el proyecto.
