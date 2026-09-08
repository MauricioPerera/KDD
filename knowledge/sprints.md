---
type: 'Concept'
title: 'Sprints orientados a resultados'
description: 'Protocolo opt-in para seleccionar backlog, admitir trabajo y medir consumo por resultado aceptado.'
tags: ['sprints', 'planificacion', 'backlog', 'tokens']
---

# Sprints orientados a resultados

Estado: protocolo piloto opt-in. La hipotesis es que seleccionar una entrega acotada
reduce exploracion y retrabajo sin debilitar las garantias de KDD. No hay ahorro medido
ni gate automatico de sprints, presupuesto o admision en esta version.

Hay una [prueba ejecutable de admision](./contracts/sprint-admission.md):
`python -m src.sprint_admission examples/sprints/admit.json`. Comprueba un snapshot
JSON de seleccion, dependencias y presupuesto; no aplica controles al despachador
ni reserva consumo. No es un gate integrado del tablero ni valida este documento.

## Relacion con KDD

El sprint selecciona el trabajo que contribuye a un resultado del proyecto durante
una ventana de tiempo definida. Referencia los contratos de la
[metodologia de ejecucion](./metodologia-ejecucion.md), sin copiar sus requisitos.
Un contrato de ejecucion puede atravesar varios sprints: cada sprint identifica la
entrega parcial que acepta. Los criterios de calidad siguen en
[validacion](./validacion.md) y [aprobacion integrada](./quality-approval.md).

Cada equipo o frente tiene como maximo un sprint activo. Frentes concurrentes nombran
un responsable de integracion y resuelven dependencias compartidas antes de iniciar.
El tablero conserva sus estados; la pertenencia a sprint es una relacion separada.
Hoy se registra en el documento del sprint: KDD-Board todavia no interpreta esa relacion.

## Artefactos y responsables

Usar `specs/sprints/TEMPLATE-SPRINT.md` para crear `SPRINT-NN-slug.md` en ese directorio.
El mismo documento contiene seleccion, cambios y cierre; los logs y reportes de los
contratos siguen en sus ubicaciones existentes. `validate_specs.py` no valida sprints.
El responsable de producto aprueba objetivo, seleccion y cambios de alcance; el
coordinador registra admisiones y consumo; el revisor acepta la evidencia integrada.
Una persona puede cubrir varios roles, dejandolo explicitado.

## Preparar y priorizar

1. Definir un resultado observable, por que importa ahora y fecha de revision final.
2. Mantener el backlog lejano breve: identificador, problema, valor y dependencia conocida.
   Elaborar contratos solo para el trabajo proximo a ser admitido.
3. Ordenar bloqueantes del resultado, entrega minima integrada y mejoras opcionales.
   Registrar una razon por inclusion; el responsable resuelve empates. Una dependencia
   externa no satisfecha impide admision aunque la tarea tenga prioridad alta.
4. Definir exclusiones y comprobar capacidad de implementacion, revision e integracion.
   Arranque del piloto: una tarea activa por agente; WIP total fijado por capacidad de
   revision y conflictos de archivos. No aumentar concurrencia solo porque haya agentes libres.
5. Separar trabajo comprometido de candidatos. Los candidatos permanecen en backlog.

## Admision antes de ejecutar

El coordinador registra fecha, tarea, revision del contrato y resultado de cada check:

- Pertenencia a la seleccion vigente del sprint y contribucion explicita al objetivo.
  Una tarea relacionada pero no seleccionada no se admite automaticamente. Una excepcion
  exige registrar el cambio de seleccion, responsable, motivo y coste antes de despachar.
- Contrato valido, criterio de aceptacion comprobable y dependencias satisfechas.
- Contexto suficiente: objetivo, contrato, invariantes y nodos relevantes. El ensamblador
  existente ayuda a presupuestar contexto, pero no filtra automaticamente por sprint.
- Perimetro compatible con las tareas activas y capacidad de revision disponible.
- Presupuesto restante suficiente para el siguiente bloque y su verificacion.
- Condicion de parada y evidencia de salida definidas.

Un check pendiente impide iniciar esa tarea; no impide ejecutar otra ya admitida.
Una investigacion puede admitirse como tarea con pregunta concreta, limite de tiempo
o consumo y salida esperada: evidencia, decision o demostracion del bloqueo.

## Consumo y parada

El presupuesto del sprint se llama `consumption_budget`; no modifica el `budget` de
complejidad de los contratos CCDD. Separar limite de contexto por llamada, consumo
acumulado y coste monetario cuando este disponible. Incluir planificacion, contexto,
implementacion, revision, reintentos, investigacion y cierre, incluso de tareas fallidas.

Registrar por ejecucion: ID unico, tarea, fase, proveedor/modelo, tokens reportados,
coste si existe, fuente y calidad de medicion (`observed`, `estimated`, `unknown`).
Mantener categorias del proveedor; no sumar tokens en cache o razonamiento dos veces
si ya estan incluidos en un total. Registrar llamadas de coordinador y agentes sin
duplicarlas; consumo compartido se atribuye una vez al sprint. No comparar costes de
modelos distintos usando solo tokens. Ausencia de telemetria es `unknown`, nunca cero.

Fijar el limite y reserva de verificacion antes de activar. Antes de cada nuevo bloque,
comprobar consumo acumulado mas estimacion del bloque y reserva restante DESPUES del
bloque contra el limite. Durante implementacion se conserva la reserva completa;
cuando el bloque es verificacion, su coste consume esa reserva y no se cuenta dos veces.
Ejemplo sintetico en una sola unidad: limite 100, consumido 80, reserva 20. Un bloque
de implementacion de 1 no cabe (80 + 1 + 20 > 100); un bloque de verificacion de 20
que completa los controles pendientes si cabe (80 + 20 + 0 = 100). Si hay mas controles
pendientes, conservar tambien la reserva necesaria para ellos. Actualizar con consumo
real tras cada bloque; la estimacion nunca equivale a consumo observado.
Alcanzar el limite detiene nuevas ejecuciones y obliga a revisar alcance o presupuesto.
La reserva no autoriza exceder el total ni omitir controles de calidad.
Sin telemetria y capacidad de interrumpir llamadas, el limite es operativo, no un tope
tecnico garantizado. Usar adicionalmente limites observables de llamadas, intentos o
tiempo; documentar sobreconsumo de una llamada en curso y detener el siguiente despacho.

Pausar la tarea afectada ante dependencia perdida, necesidad de ampliar perimetro,
evidencia invalidada o agotamiento del limite de intentos sin evidencia nueva.
Otras tareas pueden continuar si pasan admision y no dependen de la afectada. Pausar
el sprint completo cuando falta presupuesto global, el objetivo deja de ser viable
con la seleccion vigente o un bloqueo compartido impide todas las tareas restantes.
Registrar el bloqueo de tarea aqui; no inventar un nuevo estado de KDD-Board.
Guardar estado,
hallazgo, consumo y decision necesaria. El coordinador puede resolver bloqueos tecnicos
dentro del alcance; cambios de objetivo, alcance o presupuesto los decide el responsable.

## Cambios y cierre

Un hallazgo nuevo entra al backlog. Para incluirlo en el sprint, registrar quien decide,
motivo, trabajo desplazado (o capacidad libre demostrada) e impacto en presupuesto.
Una urgencia puede pausar el sprint; no habilita expansion silenciosa del alcance.

Estados del sprint: `draft`, `active`, `paused`, `closed`, `cancelled`.
`draft` pasa a `active` con seleccion, presupuesto y responsables completos;
`paused` vuelve a `active` tras registrar resolucion y nueva comprobacion de admision.
Cerrar al demostrar el resultado o llegar a la fecha de revision. El cierre declara
`achieved`, `partial` o `not_achieved`, evidencia integrada, revision del repositorio,
consumo y pendientes. `closed` no significa aprobado. Cancelar requiere motivo y
registro de trabajo/consumo hasta ese momento. Repriorizar pendientes: no arrastrarlos
automaticamente al sprint siguiente ni reabrir el cierre para ocultar un fallo.

## Evaluar el piloto

Aplicar a tres entregas del mismo frente. Antes de iniciar, elegir entregas historicas
comparables por alcance, riesgo y stack como referencia. Registrar tambien modelo,
calidad del contexto y cambios de herramientas. Si falta historial util, la primera
entrega crea una linea base descriptiva; no demuestra un efecto causal.

Comparar consumo total por resultado integrado aceptado, fraccion de retrabajo,
coste de planificacion y ejecuciones iniciadas fuera del objetivo sin excepcion.
Definir retrabajo como correccion de trabajo rechazado o repetido por contexto incompleto;
marcar esa categoria junto a la fase, sin sumar el consumo otra vez. Mostrar por separado
consumo fallido y numero de resultados aceptados. Con cero aceptados, la razon no es
calculable; no informar cero ni ocultar el consumo. No usar tarjetas como denominador.

Fijar antes del piloto el umbral de mejora esperado y los controles de calidad que
deben mantenerse. Registrar regresiones detectadas durante una ventana posterior
igual para todas las entregas. El responsable decide mantener, ajustar o retirar el
protocolo; una muestra pequena solo aporta una senal preliminar.

## Automatizacion posterior

Solo tras revisar el piloto: relacion sprint-tarea en el tablero, comprobacion de admision
en cada entrada HTTP/MCP/CLI que pueda iniciar trabajo, registro central de ejecuciones y
reserva atomica de presupuesto para concurrencia. Un campo visual o un validador de
Markdown no impide por si mismo despachos fuera de alcance. Esas capacidades requieren
contratos y pruebas propios; no estan implementadas aqui.
