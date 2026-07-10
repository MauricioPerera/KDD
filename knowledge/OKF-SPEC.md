---
type: 'Concept'
title: 'Especificación OKF'
description: 'Spec normativa mínima de OKF para la plantilla KDD: nodos, frontmatter, tipos, enlazado e indexado.'
tags: ['okf', 'spec', 'reference']
---

# OKF-SPEC — Open Knowledge Format (especificación de referencia)

OKF modela el conocimiento como **nodos**: archivos Markdown bajo `knowledge/`, interconectados por enlaces relativos. Esta es la spec normativa mínima para la plantilla KDD.

## 1. Nodo OKF

Un **nodo** es un archivo `.md` ubicado bajo `knowledge/` cuyo bloque inicial es **frontmatter YAML válido** delimitado por dos líneas `---`.

Reglas:
- El frontmatter **debe** estar presente y ser parseable como YAML.
- Tras el frontmatter sigue el cuerpo Markdown del nodo.
- Un nodo **debe** poder enlazarse desde `knowledge/index.md` (ver §5).

## 2. Frontmatter mínimo obligatorio

Todo nodo debe incluir estas claves, sin excepción:

| Clave         | Tipo     | Obligatoria | Descripción                                           |
|---------------|----------|-------------|-------------------------------------------------------|
| `type`        | string   | sí          | Uno de los tipos reconocidos (ver §3).                |
| `title`       | string   | sí          | Título humano del nodo.                               |
| `description` | string   | sí          | Resumen de una línea del contenido del nodo.          |
| `tags`        | string[] | sí          | Lista no vacía de etiquetas en minúsculas.            |

Claves adicionales (p. ej. `task`, `target`, `signature` en los contratos) son **permitidas** y específicas de cada tipo; esta spec no las restringe.

## 3. Tipos de nodo reconocidos

`type` debe ser exactamente uno de:

- `'Task Contract'` — contrato determinista para un agente efímero (CCDD). Vive típicamente bajo `knowledge/contracts/`.
- `'Data Model'` — modelo de datos (tablas, esquemas, entidades). Vive bajo `knowledge/data_models/`.
- `'Architecture'` — componente o vista de arquitectura del sistema. Vive bajo `knowledge/architecture/`.
- `'Concept'` — definición conceptual o especificación de referencia (esta spec lo es).

Cualquier otro valor de `type` se considera **inválido** para la plantilla.

## 4. Reglas de enlazado

- Los enlaces entre nodos son **enlaces Markdown relativos** (p. ej. `[texto](../architecture/overview.md)`).
- **Prohibido duplicar contenido de otro nodo.** Si la información ya vive en otro nodo, se **enlaza** al nodo fuente en lugar de reproducirla.
- Un enlace debe apuntar, dentro de `knowledge/`, a un archivo `.md` existente o a una carpeta existente. Un archivo existente con otra extensión (p. ej. `.txt`) es un enlace inválido. No se enlazan rutas externas al bundle como si fueran nodos.

## 5. Regla de indexado

- Todo nodo nuevo **debe** enlazarse desde `knowledge/index.md` (sección correspondiente a su carpeta/tipo).
- `index.md` es el catálogo de entrada al bundle; un nodo no enlazado desde `index.md` se considera huérfano.

## 6. Conformidad

Un nodo es **OKF-válido** si cumple simultáneamente: §1 (formato nodo), §2 (frontmatter mínimo), §3 (`type` reconocido), §4 (enlaces relativos, sin duplicación) y §5 (enlazado desde `index.md`).