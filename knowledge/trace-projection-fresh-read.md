---
type: 'Concept'
title: 'Propuesta de lectura fresca en la proyeccion Git'
description: 'Reducir procesos en una frontera de lectura observada sin adelantar comprobaciones.'
tags: ['traceability', 'performance', 'evidence']
---

# Propuesta y alcance

El [contrato](contracts/trace-projection-fresh-read.md) conserva el orden de
la [proyeccion](requirements-traceability.md). El lector de metadatos ya
existente puede obtener modo y contenido juntos para la ruta solicitada.
La propuesta no reutiliza comprobaciones de etapas anteriores ni precarga
datos de tareas, historia, producto o manifiestos.

## Evidencia de partida

El CI del head3655024 pasa los cuatro jobs funcionales y las dos suites por
sistema, con2107 IDs exactos. Init Windows mide567.646583s, por encima del
objetivo480s. Se conserva el fallo; no se repite ese head buscando suerte.
El modulo task_committed_artifacts mide177.378s en el post-init remoto.
Un diagnostico local de sus19 casos sin modificar registra1732 procesos Git:
440 cat-file,317 ls-tree y299 rev-parse. Los19 pasan, sinSKIP; el diagnostico
con Trace2 y afinidad4 dura97.269s. Son costes observados, no ahorro prometido.

## Diferencia frente a la optimizacion retirada

La propuesta anterior que precargaba rutas para etapas futuras no conservo
reemplazos tardios. Esta propuesta inicia una lectura nueva cuando blob pide
la ruta. Conserva los oraculos anteriores, incluidos los reemplazos durante
la proyeccion, y debe pasar todos antes de publicarse.

## Controles y coste de las primitivas

Tres metodos nuevos conservan2107 IDs y suman2110. La fase roja en Windows y
Ubuntu, tambien en copias realmente inicializadas sin.git, registra los
mismos cuatro fallos de asercion, sin errores niSKIP: dos formatos aun usan
2procesos frente a1, y las dos senales de fallback aun no conectan el lector.
Los valores, modos, reemplazo tardio y corrupcion/recuperacion pasan.
El control de fallback inyecta solamente la senal de capacidad del helper;
el camino serial conserva sus consultas Git reales.

La comparacion de primitivas existentes, sin implementar la propuesta, mide
20lecturas por tanda en Windows: serial/metadatos/serial =
1.809/0.864/2.174s y40/20/40procesos. Excluye la comprobacion inicial del
formato del repo en ambas vias. No es una medicion de modulo, post-init o CI,
ni prueba que el ahorro neto alcance480s. El nuevo oraculo tambien costara
al ejecutarse. La adopcion necesita medir su efecto neto completo.

## Estado y medicion posterior

Draft: la implementacion sigue intacta. Se requiere baseline revisado segun
[quality-approval](quality-approval.md). Despues: medir lecturas y modulo
completo, regresion Windows/Ubuntu con ambas suites y CI del mismo head final.
No atribuir al ahorro aislado el cumplimiento de480s; conservar fallos.
No se cambian timeout600, presupuesto62, runtime74d357f ni protecciones.
