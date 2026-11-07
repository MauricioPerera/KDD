---
type: 'Concept'
title: 'Lecturas agrupadas dentro de cada etapa de trazabilidad'
description: 'Reducir procesos Git de una misma etapa conservando sus limites de frescura y la validacion completa.'
tags: ['ci', 'windows', 'performance', 'traceability']
---

# Objetivo y evidencia de partida

Completar el post-init Windows en **menos de 480 segundos en cada uno de tres
CI completos consecutivos del mismo SHA final**. Conservar Ubuntu/Windows,
dos pasadas, los 2.123 IDs actuales, sus aserciones, los SKIP aplicables,
workers, timeout operativo de 600 s y presupuesto seguro de 62 procesos.
Una muestra que incumple rompe la secuencia; conservarla. El verde funcional,
una mediana o el tiempo de la suite interna no sustituyen ese criterio.

En main `0403dbf`, los intentos [1](https://github.com/MauricioPerera/KDD/actions/runs/42382220567/attempts/1),
[2](https://github.com/MauricioPerera/KDD/actions/runs/42382220567/attempts/2) y
[3](https://github.com/MauricioPerera/KDD/actions/runs/42382220567/attempts/3)
pasaron funcionalmente con post-init Windows 427,2462605 / 482,0197431 /
461,9526644 s. La muestra lenta acumula 3.732,580426 segundos de modulos
con ocho workers. Requiere reducir trabajo, conservando la auditoria.

El modulo test_task_committed_artifacts registra 160,65 s de mediana en esas
tres muestras. Un control local de sus 19 casos, todos verdes, observa 1.579
procesos Git, incluidos 499 cat-file. Su tiempo local no acredita el objetivo
remoto. Se ensayan dos reducciones mediante primitivas existentes:

- [Blobs del par de contrato](contracts/trace-contract-content-batch.md):
  conservar la consulta de modos y leer los dos contenidos solicitados juntos.
- [Comparacion fresca de artefactos](contracts/trace-fresh-stage-batch.md):
  consultar conjuntamente los datos frios que la etapa de frescura consume.

Un segundo perfil de esos mismos 19 casos conserva 1.579 procesos y observa
18 pares frios y 14 comparaciones con tres entradas frias: ahorro candidato
de 46 procesos en ese modulo, todavia sin implementar. Es una reduccion
acotada; no se extrapola a 480 s. El oraculo agrega solo tres regresiones y
reutiliza controles anteriores intactos para no inflar trabajo duplicado.

## Limites de seguridad y comprobacion

Cada agrupacion vive dentro de la etapa que ya solicita esos datos. Conservar
el orden entre manifiesto, tareas, auditoria, evidencia, producto y aprobacion.
No adelantar lecturas de etapas futuras ni reutilizar pruebas anteriores de
modo o contenido del cache de task_git. Conservar el cache de la proyeccion,
sus entradas previas y el fallback serial; no crear caches ni procesos Git
persistentes. Los cambios tardios de git replace deben seguir detectandose.

Los contratos usan un oraculo Git real compartido. Mantener intactos los
oraculos existentes, incluido el que exige una consulta ls-tree para el par.
Registrar fase roja en Windows/Ubuntu, SHA-1/SHA-256, errores y recuperacion.
El control de atomicidad no admite publicar parte de un lote invalido.

Despues del baseline revisado segun [quality-approval](quality-approval.md):
implementar, comparar original/propuesta/original con los mismos casos y
ejecutar regresion completa por sistema. Publicar un PR de medicion y verificar
tres workflows completos del mismo head, inventarios exactos y tiempos del
comando entero. Si no cumplen, conservar resultados y continuar dentro del
perimetro revisado; una ampliacion requiere otro contrato y revision.
No fusionar ni modificar protecciones. Runtime y workflows permanecen intactos.

## Implementacion y medida local

El baseline eb5be8f1fbb636a7945123900cfeb5676c1796a4 fue revisado antes de
implementar las dos agrupaciones. Pasan los tres controles nuevos y los 21
controles previos en Windows y Ubuntu; tambien la copia inicializada sin Git.
Los contenidos del par y de la etapa fresca se publican solo tras completar
el lote. Se conservan la consulta de modos, los valores retenidos y el fallback.

En los 19 casos de test_task_committed_artifacts, Trace2 mide 1579 -> 1545
procesos Git: 34 menos, todos cat-file. El ahorro observado es menor que los
46 candidatos porque algunas lecturas ya reutilizaban contenido existente.
La comparacion local original/propuesta/original tarda 95,974 / 87,673 / 92,170 s,
sin errores ni SKIP. No acredita el objetivo remoto: faltan la regresion completa
y tres CI consecutivos del mismo SHA con cada comando Windows por debajo de 480 s.
