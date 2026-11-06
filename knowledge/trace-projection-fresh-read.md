---
type: 'Concept'
title: 'Lectura fresca en la proyeccion Git'
description: 'Lectura puntual implementada con regresion local completa y aceptacion remota por medir.'
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

El baseline c2ec2da2e199b1d511bc30923eb58ec924330c54 fue aprobado conforme a
[quality-approval](quality-approval.md). La implementacion conserva la lectura
serial para entradas incompatibles y su primer error; un error de metadatos
no se convierte en exito aunque otra lectura llegue a funcionar. Ningun dato
parcial se guarda en la proyeccion. No se guardan pruebas de modo para saltar
comprobaciones futuras. El predicado existente de solapamiento se extrajo sin
cambiar su expresion para cumplir el presupuesto14; no se relajo el limite.

## Verificacion local del candidato

Ambos sistemas pasan las23etapas:19gates,184contratos,baseline,sellos y dos
suites con2110IDs exactos. Se conservaron tambien los IDs y motivos de los
SKIP anteriores:9Windows/10Ubuntu. Los179modulos post-init anteriores
conservan sus cantidades de casos ySKIP; se agrega el modulo nuevo de3casos.
El post-init ejecuta2006casos/180modulos sin omisiones ni fallos.

| Medicion local | Windows | Ubuntu |
| --- | ---: | ---: |
| Comando init completo | 340.504742s | 145.968876s |
| Post-init | 324.996846s | 143.672464s |
| Primera suite2110 | 407.446423s | 152.822724s |
| Segunda suite2110 | 419.959640s | 135.932110s |

Los24controles dirigidos pasan porOS, incluidos reemplazos tardios y modos.
El SDK fijado1.30.0 pasa sus8casos reales sinSKIP; Board pasa typecheck y
86casos sinSKIP porOS. Se conservan todos los oraculos previos.

El modulo task_committed_artifacts conserva19casos y reduce1732->1605
procesos Git. Comparacion local original/propuesta/original:
97.268909/85.445353/95.729972s; tres tandas PASS con Trace2 y afinidad4.
Las validaciones completas compartieron el host parcialmente. No atribuir
sus tiempos a una mejora causal ni usar el ahorro aislado como prueba de480s.

## Aceptacion remota

La publicacion conserva los commits existentes del PR161 y el registro
externo de aprobaciones. Las muestras remotas y sus limites se documentan en
el PR y los informes de medicion. El objetivo requiere tres workflows completos
consecutivos del mismo head final, cuatro jobs funcionales PASS, inventarios
exactos y initWindows<480s en cada intento. Un head que falle conserva la
muestra; no se repite por suerte. Al publicar esta evidencia local, ese
criterio remoto aun no estaba acreditado.

No se cambian timeout600, presupuesto62, Ubuntu/Windows, ambas pasadas,
runtime74d357f ni protecciones. No incluye fusion ni excepciones.
