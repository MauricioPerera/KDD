---
type: 'Architecture'
title: 'Precondicion observable de los fixtures de procesos'
description: 'Separar arranque observable, deadline de prueba y deteccion de supervivientes sin modificar el runtime ni omitir fallos.'
tags: ['testing', 'processes', 'reliability']
---

# Problema observado

El CI de main 924885e fallo en Windows dos veces: primero en la prueba directa
de pipes y despues en la variante MCP dentro de la copia inicializada. Ambas
fallaron porque hijo y nieto no se observaron antes de 1,5 s. Las aserciones de
cancelacion no llegaron a ejecutarse. Son resultados inconclusos para esa
garantia; no se convierten en PASS ni se repite indefinidamente hasta verde.

El [runtime](contracts/process-tree-timeout.md) conserva su deadline desde el
lanzamiento y su gracia maxima de limpieza de 5 s. No se cambia ese codigo,
sus defaults, el paralelismo ni las dos pasadas de la suite.

# Fixture revisable

La [regresion del fixture](contracts/process-fixture-readiness.md) usa 5 s de
deadline para los casos que necesitan observar descendientes. Padre, hijo y
nieto permanecen vivos durante un handshake: cada descendiente crea su marcador,
el padre comprueba ambos y crea tree.ready antes de liberar el posible efecto
tardio. No se acepta ausencia de marcadores ni se agrega skip/retry interno.

El test programa escrituras en un instante monotonic absoluto, compartido por
los procesos. Los casos normales escriben despues de deadline+2 s; el de pipes
despues de deadline+7 s, mas alla de la gracia permitida. La espera del oraculo
cubre ese instante mas 1 s. Las aserciones de ausencia de escrituras y limite
de retorno permanecen: deadline+5 s de gracia+1 s de tolerancia de medicion,
la misma formula que antes era 1,5+6=7,5 s.

Python 3.11 documenta el reloj monotonic como comun al sistema y no afectado por
cambios del reloj de pared: [documentacion oficial](https://docs.python.org/3.11/library/time.html#time.monotonic).
El timeout del runtime no empieza despues del handshake: sigue incluyendo
todo el lanzamiento. Si no hay arranque observable dentro de 5 s, el caso falla.

# Fuerza del oraculo

Se mantienen los nueve metodos anteriores y todas sus aserciones. El oraculo
adicional ejecuta procesos reales con un retraso controlado de 2 s antes de crear
descendientes: debe verificar cancelacion con la fixture nueva, y reproduce la
precondicion fallida con la anterior. Un control negativo usa subprocess.run
real sin contencion: debe ser rechazado por una escritura tardia, no por falta
de arranque. Otro caso conserva el deadline corto de 1,5 s con un objetivo que
aun no esta listo y comprueba que expira, sin ampliar la gracia del producto.

No se eliminan checks, se agregan skips o se sustituye el ciclo de vida con
PIDs simulados. El coste mayor de espera del fixture se mide y declara. Cambiar
este oraculo requiere un SHA revisado segun [calidad](quality-approval.md).
Mientras no se apruebe, main 924885e y su historial permanecen intactos, con el
CI fallido y Pages sin desplegar. La propuesta vive en una rama local separada.
