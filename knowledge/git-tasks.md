---
type: 'Concept'
title: 'Tareas OKF con historial Git'
description: 'MVP local de tareas oficiales en main, ramas por tarea y estados registrados con commits.'
tags: ['tasks', 'git', 'workflow']
---

# Tareas con Git

La fuente oficial es main: [modelo Task](data_models/git-task.md).
El seguimiento no modifica el [contrato aprobado](contracts/task-model.md)
ni sustituye la [aprobacion de calidad](quality-approval.md).
La [integracion de KDD-Board](board-git.md) consume este mismo diario mediante
HTTP y WebMCP; los proyectos Git no guardan estados en JSON.

## Uso

Desde un repositorio Git con rama main, identidad de autor configurada y
arbol/indice limpios:

```text
python scripts/tasks.py create TASK-001 --title "Validar usuarios" --description "Cerrar validacion de usuarios" --contract knowledge/contracts/validate-user-record.md
python scripts/tasks.py ready TASK-001 --approved-ref SHA_COMPLETO_APROBADO
python scripts/tasks.py start TASK-001 --assignee equipo
python scripts/tasks.py block TASK-001 --reason "Falta decision de producto"
python scripts/tasks.py resume TASK-001 --reason "Decision registrada"
python scripts/tasks.py start TASK-001 --assignee equipo
python scripts/tasks.py list
python scripts/tasks.py show TASK-001
python scripts/tasks.py history TASK-001
```

create admite --depends-on TASK-NNN repetido. Las consultas admiten --json;
--repo-root DIR es una opcion global. No cambian el checkout. Un segundo
inicio tras resume reutiliza la rama, sin borrarla ni resetear sus commits.

El coordinador o humano cambia a task/TASK-001 para implementar y registrar
sus cambios. Despues integra esa rama en main con el flujo de revision del
proyecto. La CLI no realiza merge, push ni cambia protecciones de ramas.
Para preservar el recorrido original, integrar conservando los commits;
un squash no mantiene la relacion de ancestros exigida por finish.

```text
python scripts/tasks.py finish TASK-001
python scripts/validate_tasks.py
python scripts/validate_tasks.py --base-ref SHA_INICIAL --head-ref main
```

finish usa el HEAD limpio actual como revision probada, ejecuta el oraculo
aprobado y crea un commit posterior de cierre. No acepta un PASS escrito a
mano. Los errores de pruebas no cambian el estado ni generan un cierre.
Las consultas leen blobs de main, incluso ejecutadas desde task/TASK-001.

## Operacion y limites

Las mutaciones serializan coordinadores con un lock local y rechazan cambios
ajenos en indice o checkout. Respetan los hooks de commit; un fallo anterior
a publicar el commit revierte solo los archivos propios de la operacion.
No coordinar simultaneamente con herramientas externas que ignoren ese lock.

Los commits locales deben publicarse por el flujo habitual para compartir
el estado. No reescribir el historial compartido; registrar nuevas decisiones.
Con main protegido, ejecutar el coordinador mediante el mecanismo autorizado
del proyecto: la CLI no evade la politica del servidor.

En Windows usar Git for Windows en el PATH; el Git MSYS de devkitPro devuelve
rutas POSIX y no es compatible con todas las verificaciones existentes.
El control de transiciones es un paso adicional, opt-in para proyectos
adoptantes; no cambia el conjunto fijo de 19 gates del despachador.

El runner de finish tiene un limite de 120 segundos y falla sin cerrar si
se agota. Para la suite completa de infraestructura de esta plantilla, CI
usa `validate_test_commands.py knowledge/contracts . --timeout 600`: el
contrato init-project ejecuta ademas una suite completa tras inicializar
una copia y puede superar el timeout predeterminado de 180 segundos en Windows.

## Contratos de implementacion

- [Modelo puro](contracts/task-model.md).
- [Diario y evidencia](contracts/task-journal.md).
- [Validador de historial](contracts/task-validation.md).
- [CLI](contracts/task-cli.md).
