---
type: 'Architecture'
title: 'Reducir lecturas repetidas del historial de tareas'
description: 'Reutilizar pruebas positivas de ancestros y leer padres por lote dentro de una auditoria sin omitir commits.'
tags: ['git', 'performance', 'verification']
---

# Problema medido

El [cierre operativo OP-3](operational-closure.md) sigue parcial: el CI del
PR135 pasa en ambos sistemas, pero el job Windows completo tarda 1831 s
frente a 1046 s y 1432 s en las muestras de main. Esas muestras tienen
distinto inventario y variacion de host; no prueban una reduccion total.

Un perfil de solo lectura del mismo diario real de cuatro tareas, conservado
en un bundle independiente, ejecuta 542 procesos Git: 224 merge-base,
28 lecturas individuales de padres y otras lecturas de objetos. Repetirlo
desde a9062fa tarda 100.344 s en Windows y 3.164 s en Ubuntu. El perfil
anterior del mismo arbol de la demo tardo 73.562 s y 1.084 s respectivamente.
Los procesos, head de la demo y resultados son identicos; los tiempos varian.

# Pruebas de ancestros por operacion

Extender la cache de [objetos inmutables](contracts/git-read-batching.md)
ya existente. Guardar exclusivamente resultados True producidos por Git
para dos SHA completos, con clave raiz resuelta + ambos SHA. Conservar el
booleano publico de ancestor; no almacenar un False ni un error como prueba.
HEAD, nombres de ramas y otras refs simbolicas se consultan siempre de nuevo.
La longitud debe corresponder al formato de objetos nativo de Git: en un
repo SHA-1, una rama de 64 caracteres hexadecimales sigue siendo una ref
mutable, aunque tenga la forma de un SHA-256. Determinar el formato por raiz
y operacion; si no puede determinarse, usar la consulta fresca sin cache.

La vida de esa prueba es la del object_cache actual. Los contextos anidados
comparten la operacion; al salir, incluso por excepcion, se descarta. Sin
contexto cada consulta llega a Git. No crear cache global, archivo de PASS ni
estado persistente entre validaciones. Dos repositorios no comparten pruebas.
Un objeto inicialmente inexistente no debe impedir reconocerlo si aparece.

Esto presupone una operacion de lectura sobre el almacen Git estable; la
cache no coordina escrituras externas concurrentes a objetos, grafts,
shallow boundaries o replace refs. Releer cambios a refs simbolicas durante
la operacion y cambios de configuracion del grafo entre operaciones. No
presentar esta cache local como un sandbox ni como prueba autenticada.

# Padres por lote

Leer SHA y padres de cada fila de rev-list --first-parent --reverse --parents.
El listado debe incluir la base; conservar su rechazo cuando solo es un
ancestro por segunda linea. Pasar los padres leidos a la auditoria de cada
commit, sin ejecutar otra rev-list -n 1 por commit. Los merges conservan todos
sus padres reales, no solo el primero seleccionado para recorrer la linea.

Mantener la auditoria recursiva de importaciones desde su fork unico,
rechazo de merges con mas de dos padres y de forks ambiguos. No saltar commits
sin cambios netos, snapshots, transiciones, scope, borrados o evidencias.
Una eliminacion o cambio ajeno intermedio sigue fallando aunque el tip
restaure exactamente el snapshot anterior. No ejecutar codigo del candidato.

# Comprobacion y medicion

Los [dos contratos](contracts/task-ancestry-cache.md) comparten un
[oraculo de Git y Trace2 reales](contracts/task-history-parent-batch.md).
No reemplazar respuestas de Git, imprimir PASS ni agregar SKIP para cumplir
una metrica. Las pruebas funcionales de historia y sus aserciones anteriores
permanecen intactas. Las nuevas integraciones reutilizan un fixture preparado
por clase para que medir lecturas no construya otra demo completa por caso.

La fase roja debe mostrar consultas repetidas y padres individuales como
fallos de asercion, con los controles de Git correctos. Tras la aprobacion
del nuevo baseline, verificar ambas plataformas y las dos suites completas.
El runtime aprobado, sus seis archivos, workflows, limites y protecciones
quedan fuera de este cambio.

Repetir el perfil de cuatro tareas con el mismo bundle, salida y versiones:
objetivo <=380 procesos Git, cero lecturas individuales de padres y una
prueba positiva por par de SHA y operacion. Registrar antes/despues local y
CI completo sin usar limites de tiempo fragiles como aserciones. Conservar
los intentos fallidos y distinguir mejoras del caso de mejoras del job total.
El cierre de OP-3 requiere revisar ambos resultados, sin declararlo terminado
por un microbenchmark o por un CI verde aislado.
