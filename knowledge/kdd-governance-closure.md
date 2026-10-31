---
type: 'Concept'
title: 'Cerrar las brechas de gobierno de KDD'
description: 'Objetivo verificable para integrar perimetro, evidencia, aprobaciones, oraculos y contexto con responsabilidades humanas explicitas.'
tags: ['planning', 'quality', 'tasks', 'perimeter', 'governance']
---

# Objetivo acordado

Cerrar las brechas observadas entre la propuesta de KDD y sus controles, empezando
por exigir el perimetro aprobado antes de cerrar una tarea y al auditar su historial.
Solicitud del usuario: 31 de octubre de 2026. Base de esta propuesta:
`36b69a03101181160a3299549c2d173b657ade97` de main; la auditoria previa observo
`a3be4913733d869819b75275e151a7b438a57d1a` y la brecha sigue presente en main.

La [ejecucion por contratos](metodologia-ejecucion.md), la
[aprobacion independiente](quality-approval.md) y la
[frontera de confianza](verification-guarantees.md) siguen siendo normativas.
El contrato de proyecto es [CONTRACT-34](../specs/CONTRACT-34-kdd-governance-closure.md).
Este documento no declara la implementacion terminada.

## Entregas y criterio de cierre

- [ ] **KG-1: perimetro obligatorio de tareas.** El coordinador y el auditor
  historico rechazan el mismo cambio ajeno, sin ejecutar el oraculo ni publicar
  un cierre cuando el rechazo es previo. Incluye evidencia reconstruible,
  atribucion de integracion y lectura honesta del legado. Contratos:
  [cierre](contracts/task-finish-perimeter.md) e
  [historial](contracts/task-perimeter-history.md).
- [ ] **KG-2: controles coherentes por operacion.** Documentar y ejecutar una
  matriz obligatoria para ready, start, finish y aprobacion de producto.
  Las interfaces que realizan la misma operacion deben exigir los mismos
  controles; un control requerido ausente o no soportado bloquea esa operacion.
- [ ] **KG-3: oraculos revisados y adversariales.** Exigir controles estructurales
  aplicables y contramuestras aprobadas segun riesgo, con controles sanos,
  defectos exactos y estados detectado/superviviente/inconcluso separados.
  La fuerza semantica del conjunto conserva revision humana.
- [ ] **KG-4: restricciones con alcance declarado.** Cada restriccion y budget
  requerido identifica un mecanismo efectivo y evidencia, o bloquea por falta
  de soporte. Deteccion de cambios Git no se presenta como aislamiento.
- [ ] **KG-5: contexto y aprendizaje trazables.** Registrar identidades y hashes
  de las fuentes entregadas, y enlazar hallazgos aceptados con decisiones y
  pruebas. Proporcionar contexto no prueba que el modelo lo comprendio.

KG-2 a KG-5 requieren sus propios contratos y oraculos antes de implementar.
Definirlos no cierra el objetivo: cada entrega debe conservar evidencia real.

## Primera entrega: alcance aprobado frente a cambios propios

`approved_ref` selecciona las reglas; `branch_base` y la punta preservada de
implementacion delimitan el trabajo de la tarea. No comparar todo el avance
de main contra un antiguo approved_ref. Auditar los cambios de cada commit
de implementacion, aun si despues se revierten, y el aporte de su integracion
contra el padre principal. Una resolucion de merge no puede introducir rutas
ajenas. Rechazar atribucion ambigua antes de emitir un PASS.

Usar la semantica de [touch_only](contracts/perimeter-gate.md). Contar altas,
bajas, modificaciones, ambos extremos de renombres y cambios de tipo. Contrato
y oraculo aprobados permanecen protegidos. No conceder permisos genericos a
docs/ ni a knowledge/. Los commits canonicos de diario y evidencia del
coordinador conservan su comprobacion separada de
[transiciones](contracts/task-validation.md); una rama de implementacion no
adquiere ese permiso por el nombre o mensaje de un commit.

Una rama que mezcle cambios ajenos sin una atribucion comprobable requiere
separar el trabajo o revisar explicitamente su alcance. Los avances ajenos de
main, posteriores al inicio, deben poder coexistir con una tarea valida.

Los recibos nuevos agregan un objeto perimeter a la evidencia existente:
schema_version, approved_ref, branch_base, branch_tip, tested_commit y paths
ordenados. No cambiar Task v1 ni reescribir evidencia ya publicada.
El auditor vuelve a calcular el alcance desde Git, incluso si un recibo
historico no trae ese objeto; su ausencia nunca omite el control. Un recibo
presente debe coincidir con lo calculado. Una auditoria actual no afirma que
el ejecutor antiguo haya hecho esa misma comprobacion en su momento.

El chequeo inicial precede al oraculo. Despues se vuelven a comprobar HEAD,
punta de la tarea, indice, checkout y artefactos antes de publicar el cierre.
Un fallo no publica done ni evidencia canonica. No se promete revertir
efectos arbitrarios de pruebas hostiles: el ejecutor sigue siendo confiable.

## Responsabilidades

| El codigo debe garantizar | La revision humana debe decidir |
| --- | --- |
| Comparar cambios con el permiso aprobado y rechazar desviaciones observadas | Elegir el alcance y autorizar cambios de requisitos |
| Conservar contratos, oraculos y referencias; ejecutar checks reales | Aprobar el criterio y juzgar su pertinencia y suficiencia |
| Registrar resultados, versiones, limites y casos no soportados | Definir riesgos aceptables y restricciones obligatorias |
| Entregar contexto identificable y registrar decisiones enlazadas | Evaluar coherencia, relevancia y generalizacion del aprendizaje |

## Frontera de revision y conservacion

Preparar contratos y nuevos oraculos sin modificar produccion ni pruebas
congeladas anteriores. Conservar la fase roja por aserciones de comportamiento,
los controles positivos y sus salidas en .agents/logs/governance-closure/.
Presentar el commit exacto del baseline a la persona revisora antes de implementar.

Mantener las firmas publicas, presupuestos vigentes, los cinco modulos del
auditor confiable y los controles de rutas, locks, rollback, hashes e identidad.
Una necesidad de ampliar esa base o editar otro oraculo requiere otra revision.
Conservar los IDs, metodos y aserciones existentes, Ubuntu/Windows y dos pasadas.
No debilitar protecciones ni seleccionar HEAD como aprobacion implicita.
