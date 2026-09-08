# Piloto de sprints KDD

Estado: preparado, no ejecutado. Protocolo: [sprints](../../knowledge/sprints.md).
El ensayo documental previo se ejecuto: [SPRINT-00](SPRINT-00-ensayo.md).
Detecto y corrigio tres ambiguedades; no equivale a una entrega del piloto comparativo.
Usar [la plantilla](TEMPLATE-SPRINT.md) en tres entregas reales de un mismo frente.
La seleccion de esas entregas y sus presupuestos corresponde al proyecto que lo adopte.

## Preparacion previa

Completar responsable, frente, tres resultados candidatos, referencia historica,
fuente de consumo, umbral de mejora esperado y ventana de observacion de regresiones.
Conservar los mismos controles de calidad y registrar cambios de modelo/herramientas.
No activar el piloto mientras estos datos esten pendientes.

## Ejemplo de seleccion (ilustrativo)

Objetivo: un cliente puede recuperar acceso con un enlace de un solo uso.
Comprometido: emision del enlace, validacion/consumo y prueba integrada del recorrido.
Dependencia: servicio de correo disponible antes de admitir la integracion.
Excluido: redisenar el perfil y migrar el proveedor de autenticacion.
Hallazgo durante la ejecucion: mejorar el avatar va al backlog; un fallo que permite
reutilizar el enlace bloquea la aceptacion del objetivo y se trata dentro del contrato
si su perimetro lo permite, o mediante una decision registrada si requiere ampliarlo.
Son referencias conceptuales, no contratos reales listos para ejecutar.

## Rehearsal manual antes del primer sprint

| Caso | Resultado esperado |
|---|---|
| Tarea prioritaria fuera de la seleccion | No iniciar; registrar propuesta al backlog |
| Tarea seleccionada con dependencia pendiente | No admitir; evaluar otra tarea lista |
| Presupuesto sin espacio para bloque y reserva | Pausar despacho y registrar decision |
| Proveedor sin telemetria | Consumo unknown; aplicar limite alternativo |
| Todos los contratos pasan, recorrido integrado falla | Cierre partial/not_achieved, sin aprobacion |
| Hallazgo nuevo sin relacion con objetivo | Backlog, sin implementacion automatica |
| Contrato extendido en dos sprints | Referenciar entrega parcial, sin duplicar contrato |
| Revision final con tareas pendientes | Cerrar con resultado real y repriorizar pendientes |

Registrar quien reviso cada caso y cualquier ambiguedad antes de activar.
Estos casos son una comprobacion del procedimiento, no tests de un gate implementado.

## Comparacion y decision

| Entrega | Resultado aceptado | Consumo/coste y cobertura | Retrabajo | Planificacion | Desvios sin excepcion | Regresiones |
|---|---|---|---|---|---|---|
| Referencia | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| Piloto 1 | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| Piloto 2 | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| Piloto 3 | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |

Al terminar: documentar comparabilidad, limitaciones de medicion y decision del
responsable: mantener, ajustar o retirar. No atribuir causalidad ni prometer un porcentaje
de ahorro con estos datos limitados. La ampliacion del tablero queda como trabajo posterior.
