---
type: 'Data Model'
title: 'Estilo editorial de articulos'
description: 'Quinto dominio de ejemplo: reglas editoriales de un articulo de newsletter como gate determinista, con las fronteras de juicio y de render declaradas.'
tags: ['data-model', 'editorial', 'contenido', 'example']
---

# Data Model: estilo editorial de articulos

Quinto dominio de ejemplo de la plantilla: las reglas de estilo de un articulo
(newsletter, blog) que hoy suelen vivir en prosa interpretada por humanos o LLMs, en su
parte DETERMINISTA, como gate pre-publicacion. El checker vive en
[validate-article](../contracts/validate-article.md); la tabla de estilo entra por
argumento (cada editorial define la suya).

## El record: un articulo

| Campo             | Regla determinista                                                |
|-------------------|-------------------------------------------------------------------|
| `title`           | Obligatorio; largo <= `title_max`.                                |
| `body`            | Palabras en [`words_min`, `words_max`]; sin caracteres vetados (p. ej. em-dash); sin frases prohibidas (case-insensitive); sin tablas markdown; sin H1; H2 en [`h2_min`, `h2_max`]; sin URLs crudas (links con anclaje markdown); parrafos <= `paragraph_words_max` palabras. |
| `seo_description` | Obligatoria; largo en [`seo_min`, `seo_max`] caracteres.          |

## Por que este dominio es CODIGO (cuarta clase de frontera)

Las reglas editoriales son propiedades de TEXTO: longitudes, conteos, patrones. Las
familias declarativas del motor operan sobre VALORES de campos (igualdad, pertenencia,
topes numericos) — no tienen `length` ni `matches`. Cuarta clase de frontera medida de la
vertiente ("propiedades de texto"); por doctrina, solo se agregarian familias
declarativas de texto si otro dominio repite la clase. Mientras tanto: task contract con
oraculo congelado, forma C16.

## Fronteras de JUICIO (fuera del checker, por contrato)

- Calidad del hook, tono no condescendiente, humor que "emerge natural": juicio editorial
  — territorio de un juez auditado (eval Tier 2) o revision humana. Fingirlos
  deterministas seria el antipatron que la vertiente existe para impedir.
- "Parrafos de <= 4 lineas EN PANTALLA": depende del render (ancho, fuente, dispositivo).
  Se aproxima por palabras-por-parrafo (`paragraph_words_max`) y la aproximacion queda
  declarada, no escondida.
