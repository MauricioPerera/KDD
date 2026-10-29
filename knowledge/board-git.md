---
type: 'Concept'
title: 'KDD Board con tareas Git'
description: 'Contrato de integracion del tablero con el diario canonico de tareas OKF en main.'
tags: ['kdd-board', 'git', 'tasks']
---

# Integracion del tablero con Git

Iniciar con `./scripts/run_board.ps1` en PowerShell o `bash scripts/run_board.sh`
en Unix. Requiere Node 24, Python 3.11+ y Git; el launcher Windows prioriza
Git for Windows si esta instalado. La identidad de autor debe estar configurada.
El launcher imprime una URL local autenticada. No se debe incluir ese token
en nodos ni en commits.

El tablero usa el [modelo Task](data_models/git-task.md) y el
[coordinador CLI](git-tasks.md). El nodo en el commit de `main` es la fuente
de estado. No importa tareas desde `.kdd-board/tasks.json` ni crea ejemplos
en proyectos Git. Las lecturas siguen funcionando desde una rama de tarea.
Un repositorio sin `main`, con nodos invalidos o sin Git disponible falla
explicitamente; no degrada a JSON. Solo los directorios que no pertenecen a
un repositorio conservan el tablero JSON anterior, identificado como `legacy`.
Ese modo conserva las tareas existentes y empieza vacio si no las hay; no
crea ejemplos. Para usar el diario de commits, inicializa Git en el proyecto
y crea su rama `main` antes de operar tareas.

Si el directorio elegido esta dentro de otro repositorio, pero no es su raiz,
el arranque rechaza `TASK_PROJECT_ROOT`: selecciona la raiz de ese repositorio
o inicializa uno propio en el proyecto. No se crean tareas ni se modifica el
repositorio padre. Los worktrees cuya raiz coincide con el proyecto son validos.

## Proyeccion e interfaz

`GitTaskStore(projectDir)` invoca el `scripts/tasks.py` distribuido con KDD
mediante `execFile`, sin shell, con `--repo-root` fijado por el servidor.
`KDD_PYTHON` selecciona un ejecutable Python (default `python`). Cada consulta
lee de nuevo el estado confirmado, sin cache de estados. La proyeccion conserva
todos los campos canonicos y agrega `id=task_id`, `contractId=contract`,
`sourceRef=main`; no inventa prioridades, propietarios ni evidencia.

Las rutas autenticadas son:

| Ruta | Entrada / salida |
| --- | --- |
| GET /api/board | mode git o legacy, sourceRef y transiciones permitidas |
| GET /api/board/contracts | Rutas de contratos confirmados en main |
| GET /api/tasks?status=... | Proyecciones de tareas; filtro validado |
| GET /api/tasks/ID | Proyeccion y journal de commits de la tarea |
| GET /api/tasks/ID/history | Commit, estado y motivo, en orden temporal |
| POST /api/tasks | task_id, title, description, contract, depends_on opcional |
| PATCH /api/tasks/ID/status | status, approved_ref o assignee o reason segun arista |

Las mutaciones devuelven `{commit, task}` despues del commit real. El mapeo
es backlog->ready=`ready`, ready->in_progress=`start`,
in_progress->needs_human_input=`block`, needs_human_input->ready=`resume`,
in_progress->done=`finish`. Se rechaza toda otra arista, incluido repetir
estado. `ready` requiere SHA aprobado explicito; no se completa con HEAD.
`finish` ejecuta el oraculo canonico y conserva su evidencia durable.

HTTP y WebMCP usan la misma instancia del adaptador. Las tools en modo Git
son `list_tasks`, `get_task`, `create_task`, `update_task_status` y
`task_history`, con los mismos argumentos que HTTP (`task_id` identifica
una tarea). Las operaciones JSON antiguas de asignar, re-vincular contratos,
formularios, pruebas separadas y reportes se rechazan en modo Git: el cierre
verificado y su evidencia pertenecen al coordinador. El vault sigue siendo
local e independiente; no mueve tareas automaticamente en modo Git ni se
inyecta en los tests del coordinador. No se persisten secretos en nodos.

## Concurrencia y errores

El lock y las comprobaciones de main limpio pertenecen al coordinador Python.
El adaptador no hace checkout, stash, merge, init, push ni commits propios.
Errores de entrada son 400, tarea ausente 404 y precondiciones del diario 409.
Errores de infraestructura son 503. Un timeout externo de 180 segundos supera
los 120 del runner; si una respuesta se pierde, se debe refrescar main antes
de reintentar. Un reintento de estado ya confirmado se rechaza y no duplica
commits. Las lecturas agrupan nodos e historial contra un SHA de main estable;
si main cambia durante la consulta se reintenta una vez y despues falla.

HTTP conserva `error` como texto y agrega `code`, `status` y `details`.
Las tools WebMCP resuelven los errores como
`{isError:true, error:{code,message,status,details}}`. Un rechazo por dependencias
usa `TASK_DEPENDENCIES`, HTTP 409 y los campos `task_id` y
`pending_dependencies`; permite identificar los prerrequisitos pendientes.
Los errores internos devuelven un mensaje generico sin stack, tokens ni salida
de pruebas. El [contrato de errores](contracts/board-webmcp-errors.md) conserva
las salidas exitosas y exige que un rechazo no cambie el diario.

La UI ofrece solo las aristas permitidas, recoge los campos obligatorios,
muestra rama, contrato, SHA aprobado, evidencia e historial de commits. No
muestra exito antes de recibir el commit; al fallar conserva el estado real
y presenta el error. El polling no reemplaza un formulario de transicion
mientras el usuario lo esta editando.

## Verificacion

Los contratos [diario del tablero](contracts/board-git-journal.md) e
[interfaz Git](contracts/board-git-ui.md) sellan oraculos independientes antes
de implementar. Las pruebas usan repositorios temporales reales y comprueban
el historial con el [validador](contracts/task-validation.md).
