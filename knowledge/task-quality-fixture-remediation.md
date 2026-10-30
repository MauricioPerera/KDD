---
type: 'Architecture'
title: 'Escrituras de tareas, referencias de calidad y fixtures efimeros'
description: 'Cerrar los tres hallazgos reproducidos de main sin perder pruebas ni confundir ahorro local con CI.'
tags: ['tasks', 'quality', 'ci', 'verification']
---

# Alcance y orden

Corregir la escritura externa por hardlinks del diario, las referencias moviles
de las herramientas locales de calidad y el mantenimiento redundante de dos
fixtures de uso frecuente. Aplicar la [aprobacion independiente](quality-approval.md)
y conservar la [validacion](validacion.md), el [diario](git-tasks.md) y las
[referencias externas](approval-registry.md). El punto de partida es main
`ba49821cb2f31673bc83f0d5cf764510691658f4`.

## Escrituras del diario

Antes de ejecutar el oraculo de finish, crear una rama, respaldar o escribir,
comprobar todos los destinos gestionados por la operacion. Recorrer componentes
con lstat: rechazar symlinks y reparse points; un destino existente debe ser un
archivo regular con st_nlink=1. Un destino nuevo admite ancestros ordinarios y
ausencia, pero no componentes enlazados. Revalidar al publicar y restaurar.

Una ruta rechazada produce TASK_PATH y no cambia archivos propios, indice,
refs, canarios externos ni ejecuta el oraculo. Crear tarea tambien comprueba
knowledge/index.md si va a escribirlo. Conservar el flujo backlog -> ready ->
in_progress -> done, bloqueo/reanudacion, pruebas reales y commit acotado.
Un error de commit conserva el rollback de sus propios cambios y ramas.

Esto no es un sandbox para callbacks o escritores concurrentes ni autentica
al autor de un hardlink. El coordinador solo declara la frontera de sus rutas.
Contrato: [escrituras de tareas](contracts/task-write-boundary.md).

## Identidad de la aprobacion local

approve y build_baseline aceptan unicamente el OID hexadecimal completo,
canonico en minusculas, de un objeto commit que exista en el formato nativo
del repositorio. SHA-1 exige 40 caracteres; SHA-256 exige 64. Git verifica
identidad y tipo; no basta comprobar longitud ni desreferenciar un tag.

Rechazar HEAD y expresiones equivalentes, ramas/tags, abreviaturas, OIDs de
trees/blobs/tags anotados y ramas hexadecimales de longitud ajena al formato.
Un rechazo ocurre antes de ejecutar checks; no produce un manifiesto parcial.
Conservar los SHA aprobados validos, hashes LF, integridad, perimetro y las
dos vueltas de calidad. La referencia sigue siendo una decision humana.
No modificar el selector de CI ni usar un fallback a HEAD.
Contrato: [referencias locales canonicas](contracts/quality-ref-canonical.md).

## Mantenimiento de fixtures

configure_git incorpora un opt-in ephemeral=False. En ephemeral=True escribe
maintenance.auto=false y gc.auto=0 en el .git/config local del fixture, junto
con las opciones anteriores sin detach. Rechazar tipos distintos de bool.
El modo por defecto conserva el mantenimiento habilitado.

Repository y TaskProject, que solo crean repositorios temporales propios,
incorporan automatic_maintenance=False y eligen el modo efimero antes del
primer commit. Los controles dedicados al mantenimiento solicitan
automatic_maintenance=True: siguen observando los hijos reales y su salida
antes del padre mediante Trace2. ChangeContractTests conserva su modo previo.

No cambiar configuracion global/sistema, el repositorio KDD ni otros proyectos.
No alterar cuerpos/aserciones de pruebas anteriores, timeouts, limpieza,
workers, workflows ni runtime. Los ajustes de llamadas de los dos oraculos
de ciclo de vida y los tres helpers congelados requieren revision conjunta;
sus metodos y aserciones se conservan. No simular Git ni ocultar limpieza fallida.
Contrato: [presupuesto de mantenimiento](contracts/fixture-maintenance-budget.md).

## Medicion y criterios de cierre

Antes: conservar los reportes y logs de dos intentos completos del run
40625252718 sobre el mismo SHA main. El intento 1 mide Windows 31:44 y Ubuntu
7:49; contratos 15:19/2:47, suites 7:36+7:30 / 2:13+2:13. El intento 2 se
solicita antes de cambiar fuentes; conservar tambien fallos e inconclusos.

Despues: dos intentos completos del mismo head final en GitHub, con ambos OS,
dos pasadas y recibos frescos. Registrar SHA/arbol, evento, intento, limites,
workers, duracion total del workflow, jobs, lote y cada pasada. Comparar
medianas y muestras; declarar que PR agrega build de Pages y que los runners
no son hardware controlado. Un intento fallido no se cuenta como ahorro.

La correccion funcional exige las integraciones nuevas verdes y las cuatro
pasadas completas, todos los IDs anteriores, metodos y aserciones conservados,
SDK 8 sin SKIP, Board 53/53, los 19 gates y Pages. Los SKIP previos de
aplicabilidad conservan su alcance; no agregar SKIP para ocultar carencias.
La optimizacion exige cero hijos de mantenimiento en ambos fixtures efimeros,
los mismos commits/trees de producto y una mediana Windows posterior menor
que la anterior; informar tambien Ubuntu y la suma de jobs. Si no mejora el
CI, mantener abierta esa conclusion: el microbenchmark no la sustituye.

Los nuevos oraculos deben funcionar tambien desde una copia fuente sin .git
y sin test_init_project.py. En KDD todos sus casos se ejecutan sin SKIP.

## Fronteras de revision

Definir contratos, oraculos y propuesta de helpers congelados, conservar fase
roja de produccion y revisar su SHA antes de implementar el diario o calidad.
La propuesta de fixtures forma parte del baseline; no autoriza otra mutacion
posterior de esos helpers. Verificar por AST la preservacion de metodos y
aserciones anteriores y por discovery los IDs previos.

Registrar el arbol candidato con el baseline solo tras aprobacion del revisor,
conservar las diez entradas externas y el runtime 57cb3e7 aprobado. Publicar
un PR para medir requiere autorizacion; fusion y excepciones de proteccion
quedan fuera del alcance. No cambiar workflows ni los seis archivos del
runtime. PARAR y reportar si hace falta otro oraculo, runtime o proteccion.
