---
type: 'Task Contract'
title: 'Validador editorial de articulos'
description: 'Funcion pura que valida un articulo contra una tabla de estilo: largo, estructura, lexico prohibido y formato — las reglas editoriales deterministas como gate pre-publicacion.'
tags: ['ccdd', 'editorial', 'contenido', 'example']

task: validate-article
intent: "Validar un articulo contra una tabla de estilo editorial y devolver las violaciones deterministas."
target: src/validate_article.py
signature: "def validate_article(article: dict, style: dict) -> list:"
test_command: "python -m unittest tests/test_validate_article.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 3
tests: "tests/test_validate_article.py"
tests_sha256: "60d534eec89eb5ec1040f0f58b6c58fc0fd97182c20d66e817ae179980e8be83"
touch_only: ['src/validate_article.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: validate-article

## Intent
Quinto dominio de ejemplo: las reglas editoriales de un articulo (largo, estructura,
lexico, formato) como gate determinista pre-publicacion, en vez de prosa que un modelo
interpreta. Dominio y fronteras: [editorial_style](../data_models/editorial_style.md) —
las reglas de JUICIO (hook, tono, humor) quedan declaradas FUERA de este checker. Spec:
`specs/CONTRACT-23-editorial.md`.

## Interface
```python
def validate_article(article: dict, style: dict) -> list:
    """Valida `article` ({title, body, seo_description}) contra la tabla `style`.
    Devuelve violaciones legibles (vacia = conforme), cada una nombrando el campo
    (title/body/seo_description). Acumula todas; pura; determinista; nunca lanza."""
```

## Invariants
- Definiciones EXACTAS congeladas en el docstring del oraculo: palabras = split();
  parrafo = bloque separado por linea en blanco (headers no cuentan); H2 = linea '## ';
  tabla = linea cuyo primer caracter no-espacio es '|'; frase prohibida = substring
  case-insensitive; URL cruda = http(s):// no precedido por '](' .
- Checks: title obligatorio y len <= style.title_max; body con palabras en
  [words_min, words_max], sin forbidden_chars, sin forbidden_phrases, sin tablas, sin H1,
  H2 en [h2_min, h2_max], sin URLs crudas, parrafos <= paragraph_words_max palabras;
  seo_description obligatoria con largo en [seo_min, seo_max].
- La tabla de estilo entra POR ARGUMENTO (reusable para cualquier editorial, no
  hardcodea una newsletter).
- Acumula todas las violaciones; nunca lanza ante tipos arbitrarios; stdlib (se permite
  `re`); mensajes ASCII.

## Examples
- Articulo conforme -> `[]`; link markdown `[texto](https://...)` NO es URL cruda.
- Body con `—`, "Robusto" y una tabla -> >=3 violaciones que nombran `body`.
- Titulo de 61 chars con tope 60 -> violacion `title`; 60 exactos -> ok.
- `{}` -> violaciones de title, body y seo_description (nunca lanza).

## Do / Don't
- DO: una violacion por regla incumplida, nombrando campo y regla.
- DON'T: juicio (calidad del hook, tono) — fuera por contrato; red; IO; dependencias
  fuera de stdlib; tocar tests/, knowledge/ ni el motor/gate.

## Tests
(Los tests estan en `tests/test_validate_article.py`, autorados por el orquestador y
congelados: conforme, cada regla en rojo por separado, bordes exactos, acumulacion,
robustez, determinismo.)

## Constraints
- PARAR y reportar si... el oraculo congelado fuera internamente contradictorio o algun
  check exigiera juicio no determinista (pertenece a las fronteras del dominio).
