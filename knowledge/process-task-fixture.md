---
type: 'Architecture'
title: 'Arranque y causa del timeout en el fixture de tareas'
description: 'Distinguir timeout real, fallo de arranque y salida no cero en la prueba de cancelacion del oraculo de tareas.'
tags: ['testing', 'processes', 'reliability']
---

# Evidencia y alcance

El primer intento del CI del [PR133](https://github.com/MauricioPerera/KDD/pull/133),
run 40239776017, fallo en Windows antes de observar las tres marcas del arbol en
test_task_oracle_timeout_cleans_descendants. El reintento del mismo SHA y el CI
posterior de main pasaron. El fallo se conserva: no prueba limpieza de hijos ni
permite atribuir con certeza la causa a lentitud o a un error del ejecutor.

La variante de tareas carga unittest ademas del bootstrap de contencion de
Windows y los dos descendientes. El fixture actual acepta cualquier TASK_TESTS;
por eso una salida no cero despues del handshake, limpiada por el runtime, puede
pasar aunque no haya ocurrido ningun timeout. Es un defecto del oraculo, no una
demostracion de un defecto del runtime.

# Propuesta revisable

El [contrato del fixture](contracts/process-task-fixture.md) conserva los nueve
metodos y las aserciones existentes. FIXTURE_TIMEOUT sigue en 5 s para las otras
variantes. Solo la prueba de tareas usa TASK_ORACLE_TIMEOUT=15 s, contabilizados
desde antes de ejecutar el comando, sin desplazar el reloj al handshake.

El calendario de escrituras y el limite de retorno usan el timeout elegido:
efectos a timeout+2 s, observacion hasta timeout+3 s y retorno menor que
timeout+5 s de gracia+1 s de tolerancia de medicion. Los controles existentes
de pipes y deadline corto se conservan. La reserva agrega aproximadamente
10 s por ejecucion del caso de tareas; no aumenta la gracia del producto.

Un resultado aceptable exige causa TimeoutExpired en TASK_TESTS, las tres
marcas observadas al retornar, ninguna escritura tardia y retorno acotado.
Si falta readiness, el fallo nombra marcas presentes/ausentes, tiempo observado,
timeout elegido y resultado del adaptador. Una salida temprana o error de carga
no es evidencia de cancelacion. No hay skip, retry interno ni PASS inconcluso.

# Controles reales y limites

Las integraciones ejecutan el caso de tareas con arranque retrasado 6 s, una
salida real no cero despues del handshake (SystemExit(7), que unittest captura
y reporta con salida 1), un fallo real de unittest antes del
arbol, un objetivo que nunca crea descendientes y un ejecutor stdlib real sin
contencion. El ultimo debe fallar por escritura tardia despues de observar el
arbol; los fallos tempranos deben conservar su diagnostico.

Quince segundos siguen siendo un limite finito: no garantizan arranque bajo
cualquier carga. Si vence sin handshake, el caso falla y conserva la evidencia.
La medicion local y el CI son muestras, no una garantia universal contra flakiness.
El [runtime](contracts/process-tree-timeout.md), workflows, workers y protecciones
no cambian. Se mantienen Ubuntu/Windows, las dos pasadas y los IDs anteriores.

# Revision

La [politica de calidad](quality-approval.md) exige otra revision del oraculo y
un SHA explicito antes de adoptarlo o publicarlo. La propuesta se mide frente
al fixture original, incluyendo su falso PASS por salida no cero. El baseline
incluye el diff del fixture para revision; solo despues de aprobar se adoptara
esa referencia y se ejecutara la regresion completa. No se declarara verificado
mientras este pendiente.
