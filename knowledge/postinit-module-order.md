---
type: 'Concept'
title: 'Orden medido de modulos en el post-init'
description: 'Reducir la cola de modulos pesados preservando el discovery y la ejecucion completa.'
tags: ['ci', 'performance', 'bootstrap']
---

# Evidencia y alcance

La primera muestra completa de f993e5e pasa los cuatro jobs, pero init Windows
tarda 507,362 s: excede los 480 s del [objetivo](postinit-windows-runtime.md).
El job baja de 48:52 a 42:32; no es todavia el margen de cierre acordado.

La comparacion local A-B-A de escrituras de bytecode dio 284,359 / 279,488 /
280,453 s, con los mismos 1.986 IDs y 101 SKIP del perfil con SDK. Se descarta
esa configuracion: el ahorro es pequeno frente a la variacion de los controles.

Los reportes por modulo de los dos controles muestran una cola final ociosa.
Una simulacion con sus duraciones observadas reduce la planificacion de A2
de 262,326 a 245,122 s si los modulos largos empiezan antes. La suite observada
tardo 264,755 s. La simulacion mantiene duraciones constantes; no modela la
contencion ni demuestra que el runner de GitHub cumpla 480 s.

## Contratos

- [Orden opt-in](contracts/ci-module-order.md): ordenar exclusivamente jobs
  completos ya descubiertos; nunca seleccionar, omitir o importar por el perfil.
- [Aplicacion post-init](contracts/postinit-module-order.md): datos opcionales
  de prioridad solo en Windows. El [ensayo de concurrencia](contracts/postinit-windows-concurrency.md)
  define el perfil Windows. Ubuntu mantiene cuatro procesos y las dos suites
  generales mantienen sus comandos actuales.

El archivo de prioridad se deriva del promedio de duraciones de A1 y A2 del
mismo f993e5e. Se puede regenerar con mediciones nuevas sin convertirlo en un
oraculo funcional: no acredita PASS, solo ordena trabajo que debe ejecutarse.
Nombres desconocidos no se importan; nuevos modulos conservan su ejecucion.

## Resultado de la primera muestra y procedencia de costes

El candidato 9e21871 pasa los cuatro jobs del run 42107907177, pero el comando
init Windows tarda 517,754 s, frente a 507,362 s de f993e5e. El job completo
pasa de 42:32 a 43:02. No acredita una optimizacion; se conserva la muestra y
no se repite ese head para buscar un resultado favorable.

El arranque medido del mismo Git 2.56.0.windows.4 cambia de 24,192 a 45,616 ms
de mediana entre esos runners. Los costes locales no representan por si solos
el entorno remoto. Las suites generales tampoco representan el post-init:
incluyen integraciones de bootstrap que se omiten en la copia ya inicializada.
No usar sus costes sin distinguir la aplicabilidad de cada contexto.

La propuesta de [evidencia del oraculo](contracts/init-project.md) expone el
reporte real de la pasada post-init que ya existe, sin agregar otra ejecucion.
Primero se revisa el nuevo baseline del fixture; los tiempos son diagnosticos y
no permiten declarar el objetivo de 480 s sin las tres muestras completas.

## Prioridades tras los dos timeouts del PR #194

Los intentos 2 y 3 del run 43653208864 agotaron 600 s en el comando
`init-project` de Windows. Su salida no conservó el reporte por módulo
al interrumpirse. Comparamos los 511,623 s del post-init de main
(run 43556589559) con los 370,956 s del candidato `6c2606d` en Windows
local. Se asignó a cada módulo el mayor de los dos costes observados,
escalando la muestra local por la razón 511,623 / 370,956.

Según el [contrato de prioridades](contracts/postinit-goldfish-priorities.md),
los 17 módulos omitidos que superan 30 s se insertan entre trabajos de
coste comparable. Se preserva el orden relativo de las 199 prioridades
anteriores. Los seis más costosos comienzan en las seis primeras
posiciones. Con diez procesos, la simulación pasa de 572,29 a 547,63 s en
el perfil conservador y de 367,77 a 347,32 s con las duraciones locales.
Estos valores son simulaciones y el resultado de CI se mide por separado.
El [agrupamiento de lecturas de licencias](contracts/compliance-scan-git-batches.md)
reduce arranques de Git dentro de un módulo sin alterar el orden de
las fases que verifican su procedencia.

## Revision y aceptacion

La [politica de calidad](quality-approval.md) exige revisar contratos y oraculos
antes de implementar. El cambio de run_test_suite.py pertenece al bundle de
[ejecucion confiable](contracts/ci-trusted-execution.md): presentar el SHA y los
hashes del manifiesto completo para otra revision antes de registrar y publicar el runtime.
Conservar presupuesto Git 62, timeout 600, casos/aserciones, Ubuntu/Windows y
ambas pasadas. El objetivo sigue requiriendo tres workflows completos y
consecutivos del mismo head; las muestras fallidas permanecen en la evidencia.
