---
type: 'Task Contract'
title: 'Compilacion reproducible de GitHub Pages'
description: 'Construye Pages desde fuentes publicas rastreadas en main, actualiza cifras verificables y valida el bundle bajo /KDD/ antes del despliegue.'
tags: ['kdd', 'pages', 'publishing']
task: pages-build
intent: 'Eliminar la sincronizacion manual de gh-pages y desplegar solo contenido generado desde main tras CI exitoso.'
target: site/build.py
signature: 'def build_pages(repo_root: str, output_dir: str, ci_run_url: str) -> dict:'
test_command: 'python -m unittest tests/test_pages_build.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 240
  params_max: 4
tests: 'tests/test_pages_build.py'
tests_sha256: 'ff370cc1dabd9d2c7db3d3d91e613aa7f8faa7f3f094888834f91e15ed8706de'
touch_only: ['site/build.py']
deps_allowed: ['stdlib', 'Node.js', '@rckflr/llms-skills@0.4.1']
forbids: ['llm']
---

## Intent

La [validacion](../validacion.md) y la publicacion de Pages deben leer el
mismo commit de `main`. La rama `gh-pages` conserva el historial anterior,
pero deja de ser la fuente de publicacion. El build copia solo archivos
rastreados y fuentes estaticas explicitas; nunca publica `.agents/logs/`.

## Interface

```python
def build_pages(repo_root: str, output_dir: str, ci_run_url: str) -> dict:
    """Compila un directorio nuevo y devuelve conteos, rutas y URL de evidencia."""
```

CLI: `python site/build.py --output DIR --ci-run-url URL` desde el checkout.
Requiere Node.js y las dependencias de `site/package-lock.json` instaladas.
El destino debe estar ausente; el script nunca borra un arbol existente.

## Invariants

- Solo se copian `knowledge/`, `docs/reports/`, `.agents/AGENTS.md`,
  `.agents/skills/` y los dos ejemplos publicos seleccionados que Git rastrea.
- Los HTML, logo y manifest de sitio proceden de `site/` en el mismo commit.
- `llms-skills` genera snapshot, skills, llms.txt e indice firmado. Las URL
  de manifest y snapshot empiezan por `/KDD/`; `publish --check` y strict
  validate del bundle deben terminar en 0 antes de subir el artifact.
- El numero de reportes viene de los archivos publicados, el de gates de
  `LEVEL1_GATES` y el de tests del descubrimiento de la suite. La URL de
  evidencia apunta al run exitoso que disparo el workflow de Pages.
- La pagina llama a los reportes historicos por su nombre; no afirma que
  el nuevo gate de cierre los haya verificado retroactivamente.

## Examples

- Un archivo local `.agents/logs/secret.txt` no aparece en el artifact.
- Manifest con URL `/skills/x` se transforma en `/KDD/skills/x`.
- Output existente o URL de run ajena al repo -> fallo antes de publicar.

## Do / Don't

- DO: usar el lockfile de npm y un destino nuevo para cada build.
- DON'T: usar el arbol mutable de `gh-pages` como fuente canonica.
- DON'T: exponer logs locales ni claves privadas dentro del artifact.

## Tests

`tests/test_pages_build.py` cubre seleccion de archivos, exclusiones,
prefijo de URLs, cifras y entradas invalidas. El workflow ejecuta el build
real y los validadores del publisher antes del despliegue.

## Constraints

- PARAR y reportar si una URL del bundle no resuelve bajo `/KDD/`, si el
  publisher falla o si el artifact contiene datos fuera de la lista publica.
