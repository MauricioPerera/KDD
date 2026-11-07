---
type: 'Concept'
title: 'Identidad estable en el oraculo de contencion'
description: 'Observar objetos propios antes de terminar los checks sin confundir un PID reutilizado con una fuga.'
tags: ['processes', 'windows', 'fixtures', 'verification']
---

# Identidad estable en el oraculo de contencion

El primer intento de CI de `d367208` encontro el PID 3224 activo despues de
aprobar calidad. El mismo modulo paso por separado y el siguiente intento
completo paso sin cambios. El log no conserva la identidad del objeto que
ocupaba ese PID: no demuestra que se tratara del descendiente original.
Se conserva el fallo; no se atribuye retrospectivamente una causa probada.

El [oraculo anterior](contracts/quality-process-lifecycle.md) reabria PIDs
despues de que el runner terminaba. Microsoft documenta que el identificador
puede reutilizarse al liberar el objeto y sus handles, mientras un handle
retenido sigue identificando el objeto original incluso despues del exit:
[PROCESS_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-process_information),
[handles e identificadores](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers).
Ese mecanismo admite un falso rechazo bajo creacion concurrente de procesos.

## Protocolo de observacion

1. Cada hijo y nieto real anuncia readiness dentro del temporal exclusivo.
2. El observador del oraculo retiene su objeto antes de confirmar readiness.
   En Windows abre un HANDLE SYNCHRONIZE no heredable; en Linux retiene un
   pidfd del kernel (API de os o libc si el interprete no la expone).
   La confirmacion no se adelanta a la
   adquisicion del objeto. Otros POSIX conservan el control existente y no
   acreditan la garantia adicional de identidad estable.
3. El launcher espera esa confirmacion antes de devolver el control al
   verificador. El proceso sigue vivo durante la observacion inicial.
4. Al retornar calidad, el oraculo consulta inmediatamente el mismo objeto.
   Todos los objetos propios deben estar terminados; el vecino ajeno debe
   seguir vivo y completar su trabajo al recibir su liberacion.
5. Los handles/descriptores se liberan tambien ante excepciones. Una consulta
   nativa invalida produce error, nunca se interpreta como proceso muerto.

El observador pertenece a las pruebas y no se entrega al runtime. No puede
terminar los procesos propios para hacer pasar la asercion. La liberacion
del fixture solo ocurre despues de observar el resultado o al limpiar un
fallo. Se conservan los checks de escrituras tardias y del oraculo protegido.

## Alcance y evidencia

La [correccion del fixture](contracts/quality-process-observer.md) conserva
los doce metodos y todas las aserciones existentes. Agrega controles con
procesos, Git, calidad y APIs nativas reales: adquisicion antes del retorno,
observacion despues del exit, vecino independiente, fuga deliberada y
liberacion de recursos. Un control instrumentado cuenta las consultas reales
por PID; no inventa resultados del sistema operativo ni fuerza su reciclado.

No se afirma haber reproducido el reciclado exacto del PID 3224. Se reproduce
deterministicamente la consulta tardia insegura y se elimina esa consulta.
Si un objeto retenido sigue vivo con el runtime actual, la correccion del
oraculo no basta: hace falta otro contrato y revision del runtime.

Se mantienen Ubuntu/Windows, ambas suites completas, el post-init real, todos
los limites y las omisiones de aplicabilidad previas. No se agregan retries
automaticos, pausas para esperar un resultado favorable, red ni dependencias.
La fase roja, controles, diff y hashes se revisan mediante el
[protocolo de calidad](quality-approval.md) antes de adoptar el fixture.

## Estado integrado

La correccion se integro mediante [PR164](https://github.com/MauricioPerera/KDD/pull/164)
conservando el commit y baseline aprobado
`0fb9e41ec7f538bf096a45b9562007d821061cdb`. Pasaron las regresiones locales,
el CI del PR y el CI posterior de main con Ubuntu/Windows y ambas pasadas.
Las cinco integraciones nuevas se ejecutaron sin SKIP, tambien en post-init.
El [estado verificable](estado-actual-kdd.md) enlaza los runs y sus inventarios.

La publicacion registro el arbol revisado conservando las entradas anteriores;
la fusion mantuvo ese registro, el runtime aprobado, los workflows y las
protecciones sin cambios. La identidad estable elimina la consulta tardia
insegura; las observaciones verdes siguen limitadas a sus ejecuciones reales.
