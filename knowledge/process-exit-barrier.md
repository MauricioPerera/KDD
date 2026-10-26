---
type: 'Architecture'
title: 'Confirmar la terminacion antes de liberar un comando'
description: 'Esperar handles de procesos Windows propios, ademas del contador del Job, sin ampliar la gracia ni ocultar errores.'
tags: ['processes', 'windows', 'reliability']
---

# Evidencia del defecto

El [cierre operativo OP-3](operational-closure.md) exige estabilidad real.
El CI del PR135 para 148966e fallo en la limpieza del temporal del caso
test_timeout_and_missing_executable_are_failures, dentro de la copia
inicializada: WinError32, directorio todavia en uso. Pasaron sus aserciones,
pero el error de cleanup invalido el test y el contrato init-project. Las
dos suites generales Windows no se ejecutaron; no hay PASS ni medicion
completa de ese intento.

El diagnostico de solo lectura del runtime a4be2ce observo 18 procesos
todavia no senalados al retornar entre 60 invocaciones reales. No reprodujo
localmente el mismo bloqueo de directorio; demuestra una barrera incompleta,
no que todo WinError32 tenga esa causa.

Microsoft documenta que [TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject)
aplica la terminacion a los miembros y jobs hijos. La
[terminacion de procesos](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess)
es asincrona; [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)
permite comprobar su terminacion mediante un handle con SYNCHRONIZE.
Un contador de actividad es informacion contable, no esa comprobacion.

# Barrera y recursos propios

Extender la [contencion existente](contracts/process-tree-timeout.md).
Retener handles SYNCHRONIZE de los miembros del Job propio antes de terminarlo;
volver a enumerar mientras se cancela para recoger miembros concurrentes.
Usar el [listado del Job](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list),
incluidos jobs anidados, con buffer redimensionable y comprobacion de errores.
No enumerar ni cancelar procesos globales por nombre.

Antes de acreditar la limpieza: contador activo cero y todos los handles
retenidos senalados. Esperar con el plazo restante de la misma gracia de
cinco segundos. Si no puede comprobarse un miembro o la espera falla,
devolver error de limpieza; no convertirlo en TimeoutExpired normal ni PASS.
Cerrar todos los handles en exito, fallo y timeout. Reutilizar la misma
fecha limite si un error de cleanup atraviesa la ruta de excepcion; no
reiniciar otros cinco segundos.

No usar un sleep estimado, reintentos del test completo ni retries de
rmtree como prueba de terminacion. Conservar la semantica publica, los
codigos de retorno, Unicode, cwd, env y los procesos vecinos. POSIX mantiene
sus sesiones/grupos y controles existentes. La contencion sigue teniendo
los [limites declarados](ci-audit-remediation.md): no es un sandbox ni una
garantia de tiempo real frente a fallos arbitrarios del SO. La evidencia
de handles concierne a los procesos observados del Job propio.

# Oraculo y cierre

El [contrato de barrera](contracts/process-exit-barrier.md) usa procesos
reales de tres generaciones con readiness observable. En Windows retiene
handles independientes antes de cancelar y exige que ya esten senalados
cuando retorna el backend; la limpieza del fixture espera esos handles
independientemente incluso si falla la asercion. En POSIX verifica la
cancelacion del grupo, la ausencia de efectos posteriores y la semantica
publica conservada. No simular respuestas del kernel ni agregar SKIP.

Conservar todos los oraculos anteriores. Verificar tambien el caso original
de command-workers y la copia post-apply, los 19 gates, Ubuntu/Windows, las
dos suites completas, SDK real y Board. Conservar el intento remoto fallido.
El siguiente CI debe volver a comprobar la limpieza de la copia: un
microdiagnostico o un unico rerun verde no prueba por si solo el cierre.

Este cambio modifica process_tree.py, parte del bundle de seis archivos.
Primero revisar el baseline de contrato y oraculo; despues implementar y
presentar el SHA y los seis hashes finales para la aprobacion de runtime
exigida por [ejecucion confiable](contracts/ci-trusted-execution.md).
No registrar esa referencia ni publicarla como runtime aprobado sin respuesta
humana. Cualquier anclaje Git previo a actualizar la rama y la variable
remota debe formar parte del plan concreto de publicacion revisado.
La fusion y las excepciones a protecciones siguen requiriendo autorizacion.
