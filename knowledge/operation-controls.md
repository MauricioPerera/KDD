---
type: 'Concept'
title: 'Controles obligatorios por operacion'
description: 'Matriz de controles de tareas y producto con igualdad entre interfaces y limites de la reconstruccion historica.'
tags: ['governance', 'tasks', 'quality', 'verification']
---

# KG-2: misma operacion, mismos controles

Esta propuesta desarrolla KG-2 del [objetivo de gobierno](kdd-governance-closure.md).
Depende de KG-1 y de su [compatibilidad de inicializacion](governance-initialization.md).
No acredita implementacion ni sustituye la [aprobacion independiente](quality-approval.md).

| Operacion | Controles obligatorios | Evidencia y alcance |
| --- | --- | --- |
| ready | Main limpio y lock; contrato completo valido; SHA aprobado explicito y ancestro; contrato/oraculo identicos y sello valido; invocacion reconocida y ejecutable disponible | Commit de ready y approved_ref. Reconocer un runner no ejecuta el oraculo ni demuestra su fuerza. |
| start, incluido reinicio tras resume | Repetir contrato, aprobacion, integridad y soporte/disponibilidad del runner; dependencias done; rama nueva o punta preservada desde branch_base | Commit de inicio y base inmutable. No iniciar trabajo cuyo cierre requiere un ejecutor ausente o no soportado. |
| finish | Repetir contrato, aprobacion, integridad y soporte; rama integrada; perimetro de commits e integracion; oraculo real con pruebas reconocidas; referencias y artefactos comprobados despues; publicacion acotada | Recibo canonico de la revision probada. Fallo, cero pruebas, timeout, carrera o cambio de artefactos impiden done. |
| aprobacion de producto | Politica desde SHA aprobado; esquema y categorias requeridas completos; archivos protegidos intactos; perimetro real; todos los comandos obligatorios dos veces y recomprobacion tras cada uno | Resultado de verify_quality para ese candidato. Un comando ausente, no disponible o fallido bloquea. Una etiqueta no demuestra suficiencia semantica. |

No se trata de ejecutar todos los controles en todas las etapas: ready y start
no ejecutan pruebas de producto ni atribuyen cambios que aun no existen. Cada
operacion ejecuta los controles que le corresponden antes de publicar su estado.
Un contrato aprobado no puede desactivar los controles obligatorios de la matriz.

CLI, API Python, Store, HTTP y WebMCP usan el mismo coordinador de tareas.
Un rechazo de perimetro conserva TASK_PERIMETER como error de dominio seguro
409 en HTTP/WebMCP. No exponer stderr, stack, rutas internas ni secretos.
Una excepcion interna desconocida conserva TASK_UNAVAILABLE 503; no convertirla
en una violacion de perimetro ni aceptar el cambio por error.

## Lectura historica

Snapshot y rango leen el contrato y sus artefactos como objetos Git de la revision
auditada, sin ejecutar candidatos ni consultar el checkout como autoridad.
Los controles de contrato aprobado empiezan en ready; backlog admite preparacion.
Recomprueban la estructura completa y la invocacion reconocida. Un checkout
actual corregido no debe ocultar un contrato historico incompleto.

La disponibilidad del ejecutable es un hecho del entorno de ejecucion, no del
arbol Git. Auditar historia no requiere instalar hoy un runner usado antes y no
afirma retrospectivamente que estaba disponible ni que se ejecuto cada control.
Los recibos existentes y las comprobaciones reconstruibles conservan sus limites
de [procedencia y confianza](verification-guarantees.md).

## Contratos y conservacion

- [Coordinador](contracts/task-operation-controls.md): contrato completo y runner
  reconocido/disponible antes de iniciar o cerrar trabajo.
- [Historial](contracts/task-historical-controls.md): estructura e invocacion desde
  Git sin ejecutar candidatos ni depender de la instalacion de hoy.
- [Interfaces](contracts/board-perimeter-errors.md): misma causa de rechazo de
  perimetro y mismo codigo seguro por Store, HTTP y herramientas registradas.

Reutilizar el validador completo existente, sin copiar un subconjunto alternativo
de reglas. Conservar los cinco modulos confiables, firmas, budgets, oraculos
anteriores, locks, rollback, fronteras de rutas y las dos pasadas dual-OS.
Los casos de producto comprueban regresion de los controles ya existentes; no
autorizan editar verify_quality ni incorporan otro formato de politica.

Las pruebas del registro del cliente ejecutan el JavaScript real en una VM y
consumen HTTP real. No equivalen a una revision visual o a un navegador real.

## Responsabilidad humana

El codigo exige la matriz e informa fallos. La persona revisora decide el
alcance, los riesgos, la pertinencia y la suficiencia de oraculos y categorias.
KG-3 reforzara los controles estructurales y adversariales del oraculo; KG-4
exigira mecanismos para restricciones y budgets; KG-5 conservara identidades
de contexto y aprendizaje. Esta entrega no declara esas tres brechas cerradas.
