---
type: 'Data Model'
title: 'Politica de workflows'
description: 'Tercer dominio de la vertiente rule contract: politica de workflows/automatizaciones (forma n8n) como datos declarativos, incluyendo la familia each para reglas por nodo.'
tags: ['data-model', 'rule-contract', 'workflow', 'automation', 'example']
---

# Data Model: politica de workflows

Tercer dominio de la vertiente [rule contract](../rule-contract-spec.md): politica sobre
workflows/automatizaciones, con la forma del JSON de n8n (settings escalares + array de
nodos). Es el dominio que motivo la familia `each` (cuantificacion sobre colecciones): las
reglas por nodo no solo eran inexpresables con familias escalares — forzarlas con paths
punteados producia falsos positivos en todo workflow (una lista intermedia se trata como
ausente). El rule-set vive en `examples/rules/workflow-policy.rules.json`.

## El record: un workflow

| Campo                        | Tipo    | Regla                                             |
|------------------------------|---------|---------------------------------------------------|
| `name`                       | string  | Obligatorio.                                      |
| `environment`                | string  | Debe estar en la tabla `environments`.            |
| `settings.error_workflow`    | string  | Obligatorio (todo workflow maneja sus errores).   |
| `settings.execution_timeout` | number  | `> 0` y `<=` el tope del entorno.                 |
| `nodes[]`                    | lista   | Reglas POR NODO via `each` (abajo).               |
| `connections`                | dict    | Grafo de conexiones (frontera: ver abajo).        |

## Reglas por nodo (familia `each`)

- Todo nodo `httpRequest` declara `parameters.timeout` (`each` + `where` + `required`).
- Ningun nodo lleva `credentials_inline: true` — credenciales SOLO por referencia
  (`each` + `enums [false]`).
- Solo tipos de nodo permitidos: `httpRequest`, `code`, `set`, `webhook`, `if`, `merge`
  (`each` + `enums`).

## Fronteras documentadas

1. **Ciclos del grafo** (`connections`): "ningun ciclo entre nodos" es una propiedad
   GLOBAL del grafo (recorrido), no una regla por elemento — tercera clase de frontera
   medida (tras la igualdad cross-field y la cuantificacion, que `each` cerro).
   **CERRADA por codigo** (C22): el task contract [check-graph](../contracts/check-graph.md)
   la detecta con `find_graph_cycles` y su oraculo congelado — la dupla del dominio queda
   completa: datos para lo uniforme (este rule-set), codigo para lo global (el checker).
   En el rule-set sigue declarada `code_only`, que es exactamente lo que significa: se
   valida por codigo.
2. **Tipos de nodo por entorno**: el subset interno v1 de `each` no incluye familias
   keyed; la lista de tipos permitidos es global. Si un dominio futuro exige "tipos por
   entorno", esa es la evidencia para extender el subset (documentado en
   [rule-contract-spec](../rule-contract-spec.md)).
