---
type: 'Data Model'
title: 'Tarea Git versionada'
description: 'Formato Task y transiciones del seguimiento oficial en main.'
tags: ['tasks', 'git', 'okf']
---

# Task v1

Complementa [OKF](../OKF-SPEC.md). El contrato CCDD enlazado conserva su
aprobacion independiente; el estado operativo vive en otro archivo.

## Registro

Ruta exacta: `knowledge/tasks/TASK-NNN.md`, con tres o mas digitos.
Frontmatter del dialecto canonico de KDD, sin claves duplicadas:

| Campo | Regla |
| --- | --- |
| type | Task |
| title, description | Texto no vacio de una linea |
| tags | Lista no vacia de etiquetas minusculas |
| task_id | TASK-NNN; coincide con el nombre del archivo |
| status | backlog, ready, in_progress, needs_human_input o done |
| branch | task/TASK-NNN; identidad estable |
| contract | Ruta exacta knowledge/contracts/nombre.md |
| assignee | Vacio hasta iniciar; luego texto de una linea |
| depends_on | Lista sin duplicados de IDs existentes |
| approved_ref | SHA completo aprobado explicitamente al pasar a ready |
| branch_base | SHA main desde el que se creo la rama al iniciar por primera vez |
| reason | Motivo no vacio de la ultima operacion |
| verified_ref | SHA probado; vacio hasta done |
| evidence | Ruta docs/task-evidence/ID-SHA.json; vacia hasta done |
| evidence_sha256 | SHA-256 del artefacto de evidencia; vacio hasta done |

Todos los campos estan presentes, aunque los pendientes sean strings vacios.
El cuerpo enlaza al contrato mediante Markdown relativo y admite notas.
Los nodos son alcanzables desde knowledge/index.md por un enlace a tasks/.
No se guardan credenciales ni un historial duplicado dentro del nodo.

## Transiciones

- Creacion -> backlog.
- backlog -> ready: contrato e inventario de oraculos actuales validos e
  iguales al commit aprobado, que debe existir y ser ancestro de main.
- ready -> in_progress: responsable y rama asociada; dependencias done.
- in_progress -> needs_human_input: motivo del bloqueo.
- needs_human_input -> ready: motivo de resolucion; se conserva la rama.
- in_progress -> done: rama integrada y evidencia del ejecutor confiable.

No hay saltos, bajas, reapertura ni cancelacion en v1. El ID, contrato,
rama y dependencias no cambian despues de crear. approved_ref se fija una vez;
branch_base se fija en el primer inicio. done es historico: certifica la
revision indicada, no que futuros cambios del producto sigan pasando esos tests.

## Evidencia

finish ejecuta en main limpio los archivos seleccionados por python -m unittest
o node --test. El recibo v2 registra cada ruta seleccionada en `oracle_results`
con los campos `executed`, `skipped` y `ok`. Exige casos instrumentados
positivos por archivo, cero omisiones y exit 0. Conserva stdout, stderr,
conteos, comando, SHA probado, tip integrado y hashes del contrato, target,
oraculo primario y salida. Los recibos v1 de un archivo conservan su validacion
historica. El JSON se guarda fuera de knowledge/.
[Contrato de evidencia](../contracts/task-oracle-execution-proof.md).
[Inventario multiarchivo](../contracts/git-task-multi-oracle.md).
El commit de cierre solo cambia el nodo y agrega su evidencia; verified_ref
apunta al padre, evitando una referencia al propio hash futuro.

Validar un registro verifica integridad y coherencia, no autentica al
productor. El coordinador, runner, aprobacion y proteccion de main son
confiables; el codigo de prueba no esta aislado y puede falsificar salida.
La CLI no consulta GitHub ni afirma que exista aprobacion remota.

Los metadatos de seguimiento se registran por el coordinador, fuera del
perimetro del implementador. El validador audita la primera linea de padres
de main; una rama de tarea nunca es una segunda fuente de estado oficial.
