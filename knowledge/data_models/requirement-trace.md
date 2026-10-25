---
type: 'Data Model'
title: 'Manifiesto y reporte de trazabilidad v1'
description: 'Formato estricto de relaciones declaradas y evidencia derivada desde revisiones Git.'
tags: ['requirements', 'traceability', 'schema']
---

# Entradas

La [arquitectura](../requirements-traceability.md) define vigencia y confianza.
El spec es un nodo Concept de OKF con una sola seccion `## Requisitos` y lineas
`- [REQ-001] Texto observable`. ID: REQ- seguido de tres o mas digitos.
No admite IDs repetidos, textos vacios o requisitos mal formados; no interpreta
ejemplos dentro de fences como requisitos. Otras secciones pueden tener ejemplos.

El manifiesto JSON UTF-8 contiene exactamente estas claves:

```json
{
  "schema_version": 1,
  "spec": "knowledge/product-spec.md",
  "bindings": [
    {
      "requirement": "REQ-001",
      "contract": "knowledge/contracts/value.md",
      "tasks": ["TASK-001"]
    }
  ]
}
```

Version entera 1; se rechazan booleans, claves duplicadas y campos desconocidos.
spec debe ser un .md bajo knowledge/; contract un .md directo bajo
knowledge/contracts/. Son rutas relativas exactas POSIX, sin segmentos . o .., escapes,
backslash, colon, glob o controles. Los blobs de entrada, contratos, targets,
oraculos y evidencia deben ser archivos regulares, no symlinks de Git.
Un requisito tiene uno o mas bindings; no hay bindings huerfanos ni parejas
requirement/contract repetidas. tasks es una lista sin duplicados de TASK-NNN,
posiblemente vacia para planificar. Una tarea puede respaldar varios requisitos
del mismo contrato; no dos contratos distintos. El orden no es significativo.

## Huella por requisito

SHA-256 de JSON canonico con ruta del spec, ID, texto y todos sus bindings.
Claves y listas se ordenan; se usa UTF-8/JSON compacto y LF. Los requisitos
ajenos no entran en esa huella. Debe existir el mismo registro en el spec y
manifiesto de approved_ref de cada tarea aprobada enlazada. Se informa el SHA
aprobado efectivo de la tarea, sin elegir el commit observado como aprobacion.

## Reporte JSON

```json
{
  "schema_version": 1,
  "ok": true,
  "complete": false,
  "observed_commit": "SHA_COMPLETO_OBSERVADO",
  "audit_base": "",
  "manifest": "quality/traceability.json",
  "spec": "knowledge/product-spec.md",
  "requirements": [
    {"id": "REQ-001", "text": "Texto observable", "state": "pending", "links": []}
  ],
  "findings": []
}
```

Cada link contiene contract, oracle, target, task_id, task_status, approved_ref,
branch_tip, tested_commit, evidence, evidence_sha256, state e historical_verified.
Los campos aun inexistentes son strings vacios; una asignacion vacia se muestra
como un link pendiente. No se acepta ninguno de esos resultados como entrada.
findings contiene objetos code, requirement, task_id y message; orden estable.
Todo link y requisito usa pending, verified o stale; ok=false ante errores de
integridad o vigencia, y ante pendientes con --require-verified.
complete=true solo si todos los requisitos son verified.

Task.done valida el artefacto y su salida mediante el validador existente.
historical_verified distingue evidencia historica valida de vigencia actual;
no se borra cuando cambia un target actual. Los errores de entrada/Git fallan
explicitamente; un reporte vacio nunca representa aprobacion.

## Presentacion y comando

La CLI usa --repo-root, --ref (main), --manifest (quality/traceability.json),
--format json|markdown (json) y --require-verified. JSON compacto o indentado es
equivalente; el orden de requisitos y links es determinista.
Exit 0: integridad valida y completitud si fue requerida. Exit 1: relaciones,
historial o vigencia invalidos, o pendientes con --require-verified.
Exit 2: configuracion, JSON, Git o argumentos invalidos. Los argumentos validos
producen diagnostico estructurado incluso ante un error; argparse conserva su
uso convencional para argumentos incorrectos y --help.

La matriz muestra las mismas identidades, commit probado, evidencia y estado;
no llama a otro ejecutor ni imprime texto sin escapar como markup activo.
