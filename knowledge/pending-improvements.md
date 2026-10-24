---
type: 'Concept'
title: 'Cierre de pendientes de KDD'
description: 'Objetivo, contratos y criterios de cierre de seguridad, evidencia, operacion y rendimiento detectados en el piloto de dependencias.'
tags: ['roadmap', 'quality', 'git', 'ci']
---

# Objetivo y criterio de cierre

Completar los siete pendientes observados en el piloto de cuatro tareas.
Cada cambio conserva la aprobacion externa de contratos/oraculos, las
protecciones de main y el historial original. El baseline candidato no se
convierte en aprobado por ser HEAD. El avance y las mediciones reales se
registran en .agents/logs/pending-improvements-REPORT.md.

## Seguridad del tablero

[Dependencias del tablero](contracts/board-dependency-security.md): elevar el
minimo Zod a 4.6.6 en manifest y lock, compatible con fastwebmcp; comprobar la
version instalada y la validacion real en un proceso con memoria limitada.
No contar un proceso abortado por memoria/timeout como rechazo correcto.
Ejecutar typecheck y toda la suite del tablero tras instalar desde el lock.
Referencia: [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5).

## Procedencia de scans

[Bootstrap y procedencia](contracts/bootstrap-scan-provenance.md): los seis
findings de ejemplo actuales no deben llegar como evidencia del nuevo
proyecto. Remover de la copia solo los contenidos de ejemplo conocidos por
ruta y digest; conservar un informe propio incluso en la misma ruta. El
dry-run no escribe y lista los ejemplos que quitara. Los casos personalizados
no se borran por prefijo, glob ni heuristica.

En [evidencia opcional](contracts/optional-evidence.md), scanId que comienza
con example_ identifica una muestra: optional -> SKIP; required -> FAIL,
incluido outcome success. Un JSON invalido no acredita evidencia. Las reglas,
schemas y tests de validadores de scans siguen distribuidos como infraestructura.
La calidad de producto sigue siendo obligatoria y no se sustituye por scans.

## Evidencias generadas de tareas

[Calidad con evidencia de tareas](contracts/quality-task-evidence.md) extiende
opcionalmente la politica revisada con generated_task_evidence, una lista no
vacia de objetos {task_id, contract}. IDs unicos TASK-NNN y contrato exacto
bajo knowledge/contracts; el contrato y su oraculo deben estar protegidos.
No se permiten glob, prefijos de directorio, rutas ejecutables ni IDs ajenos.

La extension autoriza exclusivamente el artefacto JSON canonico de un nodo
Task done seleccionado. Ese nodo debe estar confirmado en HEAD, apuntar al
contrato declarado y a docs/task-evidence/TASK-ID-TESTED_SHA.json. Working tree,
indice y objeto Git del artefacto deben coincidir byte a byte. Se exige
integracion, sellos, output reconocido, SHA probado como padre del cierre y
diario de transiciones valido, segun el [modelo existente](data_models/git-task.md).
No se admite evidencia huerfana, fabricada, staged sin commit o de otra tarea.

El verificador usa los cinco modulos canonicos validate_tasks.py, task_git.py,
task_model.py, task_evidence.py y validate_contracts.py extraidos del commit
aprobado a un temporal externo, con imports del bundle congelado. Todos deben
figurar en protected. Nunca se importa un helper candidato ni se ejecuta el
oraculo almacenado en el reporte. Se audita desde la raiz de la cadena
first-parent hasta HEAD, incluidas importaciones, antes y despues de checks.
La politica antigua conserva su esquema, permisos exactos y comportamiento.
Cualquier cambio de politica o de oraculos sigue requiriendo revision humana.

## Errores operables por WebMCP

[Errores estructurados](contracts/board-webmcp-errors.md): mantener los
resultados exitosos de las cinco tools y el formato HTTP error string.
HTTP agrega code, status y details. Los errores de dominio invocados por
WebMCP se resuelven como {isError: true, error: {code, message, status, details}},
sin lanzar una excepcion que el navegador convierta en UnknownError.
TASK_DEPENDENCIES incluye task_id y pending_dependencies con los IDs realmente
no cerrados; no revelar tokens, entorno, stack ni secretos en errores internos.
El fallo no produce commit, rama, cambio de nodo o evidencia.

## Lecturas Git y CI

[Lecturas por lote](contracts/git-read-batching.md): agrupar lecturas de blobs
inmutables y del indice sin persistir evidencia entre invocaciones. Resolver
refs mutables de nuevo en cada operacion. Validar protocolo de cat-file,
tamanos/tipos/rutas y errores; preservar Unicode, saltos de linea y bytes
cuando correspondan. Los archivos e indice se vuelven a comprobar antes y
despues de cada check; no cachear ese estado mutable.

La auditoria historica puede reutilizar objetos solo por raiz+SHA inmutable y
dentro de una llamada. La prueba debe medir procesos Git reales: leer 12
nodos usa <=5 procesos y verificar una politica con 24 protegidos y dos checks
2x usa <=30 procesos Git, conservando rechazo de mutaciones. Medir tiempo
antes/despues en el mismo entorno y registrar tambien los conteos, sin
prometer un porcentaje de ahorro a partir de un unico run.

[Actions con Node24](contracts/ci-node24-actions.md): actualizar checkout,
setup-python y setup-node en todos los workflows y la accion compuesta si
los usan, a commits oficiales revisados que declaran runs.using node24.
Actualizar tambien configure-pages, deploy-pages y upload-pages-artifact;
para esta ultima accion compuesta verificar el runtime node24 del commit
anidado de upload-artifact. El build de Pages usa Node24.
Conservar permissions, persist-credentials:false existentes, fetch-depth:0,
la precondicion de baseline, los 19 gates, validacion de tareas, dual-OS
validate/board, Python 3.11, Node24 y los dos comandos/entornos de suite.
Conservar concurrencia y deduplicacion; no agregar continue-on-error ni
cancelar push/callers reutilizables. No modificar protecciones para probarlo.

## Regresion del piloto

[Recorrido reproducible](contracts/dependency-workflow-e2e.md): instanciar la
plantilla real en un temporal, definir producto y cuatro contratos/oraculos
propios, preparar un baseline simulado local y gestionar las transiciones
mediante el HTTP autenticado real de KDD-Board. Grafo A -> B/C -> D.
Probar rechazos antes de A y cuando solo B esta cerrada, rama conservada tras
block/resume, implementaciones reales, merges que preservan commits, cuatro
cierres y artefactos auditados, y los cuerpos Python del CI generado.
No hacer requests a GitHub ni publicar repos desde los tests; no afirmar
prueba de navegador renderizado a partir de HTTP o VM.

## Concurrencia, recuperacion y publicacion

[Worktrees y publicacion](contracts/task-worktree-integration.md): mantener un
coordinador de estados en main y trabajadores en worktrees de ramas de tarea.
Probar dos procesos de implementacion vivos a la vez, integracion de hermanos
sin perdida, conflicto real y merge --abort que conserva tips/checkout, y
lock compartido entre worktrees. Un lock que sigue presente tras una
interrupcion se conserva y bloquea hasta recuperacion explicita; nunca
borrarlo por suposicion de antiguedad ni recuperar cambios ajenos.

Un remoto bare local con hook que rechaza push directo a main y exige diario
valido permite probar publicacion/rechazo sin permisos externos. Es una
simulacion local de proteccion; la verificacion de GitHub requiere consultar
su proteccion real y verificar el PR/CI reales, sin atribuir esa garantia al
hook local. No reescribir SHAs, forzar pushes ni deshabilitar controles.

## Orden y aprobacion

La regresion completa detecto un falso positivo del patron sk- al cargar el
nombre del contrato de worktrees. El [contrato de prefijos](contracts/context-secret-prefixes.md)
delimita esa correccion de configuracion, conserva los demas controles y
agrega evidencia positiva y negativa; no modifica el oraculo del ensamblador.

1. Contratos, oraculos nuevos y fase roja/controles existentes.
2. Revision humana del SHA candidato antes de implementar.
3. Seguridad y procedencia de scans.
4. Evidencias generadas y errores WebMCP.
5. Lecturas por lote y Actions, con mediciones.
6. Piloto repetible y worktrees; verificacion de regresion y CI.
7. Informe final por criterio y limitaciones pendientes.

Las extensiones legitimas de contratos existentes se revisan con el nuevo
baseline. No se reducen ni resellan aserciones anteriores para obtener verde.
