---
type: 'Concept'
title: 'Perfil de suite Windows con seis procesos y cierre temporal completo'
description: 'Extension propuesta tras dos muestras funcionales cuyo criterio temporal completo sigue abierto.'
tags: ['ci', 'windows', 'performance', 'verification']
---

# Motivo medido

La primera iteracion de [mutaciones, aprobaciones y CI](audit-mutation-approval-ci.md)
conservo sus dos commits en PR138. Dos intentos completos del mismo head 57cb3e7
pasan los cuatro jobs funcionales, 116 contratos, 1574 IDs por pasada/SO,
SDK8 sin SKIP, Board53 y Pages. Windows mide 1978/1551 s; mediana 1764.5 s,
8.53% menor que el antes fijo de 1929 s. Ubuntu mide 435/442 s.
El objetivo completo sigue abierto: la primera muestra supera 1929 s.
No se descarta esa muestra ni se mezcla con el siguiente head.

El perfil por modulo muestra esperas reales y trabajo distribuido. Una
simulacion de ordenar por coste solo ofrece 8-9 s por pasada y no es evidencia
de ahorro. Un ensayo local del mismo clon/interprete/1574 IDs pasa con seis
workers en 707.54 s, frente a 791.66/890.02 s con cuatro. Es exploratorio,
con carga del host no controlada; no demuestra el resultado de GitHub.

# Cambio propuesto

El [contrato del perfil](contracts/ci-windows-suite-six.md) extiende exclusivamente
el default de suite Windows del [runtime](ci-runtime.md). La API existente ya
acepta 1..8. Se propone cambiar una expresion del workflow; no cambia el bundle.

| Contexto sin input explicito | Suite | Contratos |
| --- | ---: | ---: |
| KDD nativo, Windows | 6 | 4 |
| KDD nativo, Ubuntu | 4 | 4 |
| Caller reutilizable o repositorio ajeno | 1 | 1 |

Los inputs explicitos prevalecen. Un valor invalido sigue fallando antes de
ejecutar casos. Las dos pasadas conservan comando, entorno y perfil identicos,
y la segunda empieza al terminar la primera. El bootstrap sigue exclusivo
antes del lote de cuatro contratos, con 600 s, y su copia post-init mantiene
los cuatro procesos explicitos existentes. No se agregan jobs ni se amplian
timeouts. Pins, permisos, matriz y los cuatro nombres funcionales se conservan.

# Oraculos e integraciones

El nuevo oraculo interpreta solo el subconjunto booleano/string que usa la
expresion del workflow, sin eval ni funciones arbitrarias. Sigue los operadores
y comparacion de strings de la [referencia oficial de expresiones](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions).
La sintaxis completa se verifica con actionlint y el perfil efectivo con Actions.

Las integraciones extraen los seis archivos reales de un commit Git sintetico
propio a un bundle externo. Seis modulos se sincronizan en una barrera real;
comprueban seis PIDs simultaneos, fixtures de modulo/clase una vez, IDs exactos,
dos invocaciones con reportes frescos, un fallo genuino y un input invalido que
no ejecuta casos. La copia inicializada sin .git ejecuta los mismos controles;
si la fuente ya esta inicializada, no se intenta inicializarla otra vez.
No se usan mocks del filesystem, Git, procesos ni reportes.

Se adapta una comprobacion del oraculo previo de workflow: suite Windows seis
y Ubuntu cuatro, conservando contratos cuatro y defaults de consumidores uno.
Conserva todos los metodos y el numero de aserciones; los demas oraculos previos
permanecen intactos. El inventario previo completo de 1574 IDs se conserva.

# Medicion y aprobaciones

Antes sigue fijado en las tres muestras de fb04cdbf: mediana Windows 1929 s.
La primera iteracion 1978/1551 se conserva como resultado intermedio, sin
declarar cerrado OP-3. Tras implementar el nuevo perfil, exigir dos intentos
completos verdes del mismo head con cada job Windows <1929 s y mediana
<=1832.55 s. Auditar todos los IDs viejos/nuevos y las dos pasadas en Ubuntu y
Windows, SDK8, Board53, colas, suma de jobs y variacion de runners. No se afirma
causalidad exclusiva ni ahorro remoto a partir del ensayo local.

Seguir [quality-approval](quality-approval.md): baseline revisado antes de tocar
el workflow. El runtime aprobado conserva 57cb3e706b4eec756e98647e71f445dbfc6d6841
y los seis blobs. Registrar el arbol final con el nuevo baseline solo tras
autorizacion, preservando las ocho entradas actuales. Actualizar PR138
conservando sus dos commits originales. Las cinco protecciones y strict siguen
intactos; esta extension no autoriza fusion ni excepcion a trusted-pr-gate.
