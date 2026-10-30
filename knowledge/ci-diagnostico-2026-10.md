---
type: 'Concept'
title: 'Diagnostico del tiempo de CI de octubre de 2026'
description: 'Evidencia, limites y prioridades para analizar el tiempo de CI sin reducir sus garantias.'
tags: ['ci', 'performance', 'evidence']
---

# Que sabemos del tiempo de CI

Este nodo conserva el diagnostico del arbol `af680c1fd251b080c154ab2eacf62d74434a4451`.
Es una fotografia historica, no un indicador actualizado ni una promesa de
rendimiento. El [protocolo de CI](ci-runtime.md) y sus contratos siguen siendo
la fuente normativa. No se ha demostrado una nueva reduccion total del CI.

## Medicion en GitHub Actions

El [run 40648566045](https://github.com/MauricioPerera/KDD/actions/runs/40648566045)
paso para ese arbol. Los jobs de validacion y Board corrieron en Ubuntu y
Windows; la suite principal ejecuto dos pasadas por sistema con 1.636 IDs.
Cada pasada declaro 9 skips en Windows y 10 en Ubuntu; esos IDs incluyen
casos omitidos y no equivalen a 1.636 casos aprobados.

| Medida | Windows | Ubuntu |
| --- | ---: | ---: |
| Job validate | 37 min 56 s | 7 min 2 s |
| Comandos de contratos | 17 min 53 s | 2 min 30 s |
| Suite, primera pasada | 9 min 26 s | 2 min 4 s |
| Suite, segunda pasada | 9 min 12 s | 2 min 3 s |
| Job Board | 1 min 11 s | 23 s |

En Windows, los tres pasos consecutivos de contratos y suites sumaron
36 min 31 s, alrededor del 96 % del job. Son tiempos de pared por paso, no
la suma de los procesos que trabajan en paralelo. Esta muestra no demuestra
por si sola la causa de la diferencia entre sistemas.

El gate agrupo 121 contratos en 119 comandos unicos dentro de su invocacion.
Un cruce estatico entre selectores de contratos e inventario detecto 1.483 IDs
potencialmente compartidos con las suites. No acredita que todos se ejecutaran
en ambos contextos ni que sus garantias sean equivalentes; los skips y la copia
inicializada deben analizarse por separado.
En Windows, `init-project` se ejecuto en exclusiva antes del pool de cuatro
workers; sus 16 casos informaron 415,209 s de unittest. Ubuntu informo
121,621 s para esos casos, sin la misma exclusividad. Ese tiempo incluye la
creacion y validacion de un proyecto real y la suite en su copia. La
[exclusividad y limites de recursos](contracts/ci-contract-resources.md)
responden a timeouts observados; no se ha demostrado que retirarlos sea seguro.

Para ese mismo run, la salida de unittest permite atribuir tiempos parciales a
110 contratos por sistema, pero no reconstruir todos los intervalos de los
119 procesos: el resultado del gate se imprime al terminar el lote y sus
reportes temporales por comando no se publicaron. Los tiempos de unittest no
incluyen necesariamente todo el proceso. No es posible identificar el camino
critico completo de ese gate con esos datos.

## Perfil local de la copia inicializada

Una ejecucion local Windows con Python 3.11.15, parsers fijados y actionlint
verificado paso los 16 casos de `init-project` en 379,459 s. La suite de la
copia tardo 370,348 s: 120 modulos, 1.530 IDs esperados y ejecutados, 73 skips
declarados y cero errores. Esta copia tiene su propio inventario; no equivale
a una de las dos pasadas de la plantilla original. Los skips incluyen casos
de plantilla que no aplican y SDK o dependencias ausentes de ese entorno.

Otra ejecucion local envolvio el runner para registrar los intervalos de sus
120 workers. De 391,484 s entre el primer inicio y el ultimo final, cuatro
workers estuvieron activos 384,500 s. Tras el inicio del ultimo modulo
restaron 7,781 s. El envoltorio llamo `run_suite` directamente, sin el proceso
supervisor habitual, y agrego escritura de diagnostico. La ocupacion de
workers no mide uso de CPU ni de disco; es una muestra local, no CI remoto.

En esta muestra, la falta de modulos disponibles para repartir no explica una
gran cola final. Reordenarlos podria cambiar la contencion y los tiempos: un
modelo con duraciones fijas no demuestra ahorro. La instrumentacion y las
cargas locales impiden extrapolar sus porcentajes a los runners de GitHub.

Dos intentos locales anteriores fallaron por preparacion del entorno y
fixtures: uno carecia de actionlint y otro de los parsers requeridos. Se
conservaron como fallos de diagnostico, no como pruebas verdes ni como fallos
del CI de referencia. Los reportes y trazas crudas de esta investigacion
quedaron en `.agents/logs/`, que es local e ignorado por Git; este nodo no
afirma que esten disponibles en un clon nuevo.

## Costes de operaciones Git y lectura de tareas

Una traza local del piloto de cuatro tareas registro 2.145 procesos Git; 22
llamadas a `git log` coincidieron con la lectura de historiales bajo el arbol
de Board. Una consulta de historial de un fixture concreto lanzo 10 procesos
Git por CLI y 7 mediante la llamada directa; devolvieron las mismas cuatro
entradas con `main` estable. No se midio un ahorro del job completo.

La CLI lee las tareas antes de solicitar el historial, que vuelve a comprobar
su existencia. En un clon aislado, al cambiar `main` entre lecturas, los dos
caminos produjeron errores distintos: `TASK_MISSING` y `TASK_GIT`. El ensayo
no ejecuto Board HTTP. Una modificacion debe definir primero la semantica de
errores y carreras y preservar la frescura de refs y la auditoria historica.
Ver [presupuesto de lectura de main](contracts/task-main-read-budget.md) y
[coste de lectura del historial](task-history-read-cost.md).

## Preguntas abiertas y siguiente medicion

1. Registrar por comando y por worker inicio, fin, veredicto y contexto para
   identificar el camino critico real, sin interpretar la suma de procesos
   concurrentes como tiempo de pared. La instrumentacion necesita validar
   su coste y confiabilidad antes de afectar el CI.
2. Perfilar las fases y recursos de las integraciones mas largas, manteniendo
   las pruebas reales, las esperas de terminacion y sus limites. Ni el coste
   local de una copia ni el numero de procesos prueba una causa del CI remoto.
3. Comparar varias muestras equivalentes antes y despues: SHA, evento,
   intento, SO, versiones, inventarios, skips y fallos; reportar job critico,
   tiempo total y suma de jobs por separado. No atribuir causalidad a
   diferencias de runner, cache o cantidad de pruebas no controladas.
4. Para cualquier cambio futuro, definir primero contratos y oraculos,
   preservar Ubuntu/Windows, cobertura y dos pasadas, y seguir la
   [aprobacion de calidad](quality-approval.md) y el
   [protocolo de medicion](ci-runtime.md). Esta investigacion no autoriza
   cambios de runtime, protecciones ni reutilizacion de resultados entre
   pasadas.
