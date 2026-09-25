---
type: 'Task Contract'
title: 'Manifiesto determinista de baseline de calidad'
description: 'Materializa la referencia aprobada y los hashes protegidos sin elegir HEAD ni modificar el repositorio.'
tags: ['quality', 'baseline', 'security']
task: quality-baseline
intent: 'Materializa un baseline explícito de calidad.'
target: scripts/quality_baseline.py
signature: 'def build_baseline(repo_root: str, policy_path: str, approved_ref: str) -> dict:'
test_command: 'python -m unittest tests/test_quality_baseline.py'
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 160
  params_max: 3
tests: 'tests/test_quality_baseline.py'
tests_sha256: 'a1468bcf1494effceef5f5b6e66c9050ad5869e46a2b2e79db176d64f705788b'
touch_only: ['scripts/quality_baseline.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

El manifiesto hace visible qué commit y qué archivos protegidos forman la frontera
de aprobación. Se genera solo desde un SHA proporcionado por el revisor y no cambia
el índice, el working tree ni la referencia Git.

## Interface

```python
def build_baseline(repo_root: str, policy_path: str, approved_ref: str) -> dict:
    """Return the approved commit, policy hash and protected file hashes."""
```

## Invariants

- `HEAD` y referencias vacías se rechazan como baseline implícito.
- La política y los protected se leen del commit aprobado, no del working tree.
- Las rutas se validan como relativas y exactas.
- La salida contiene un SHA de política y un SHA por archivo protegido.
- La operación es de solo lectura respecto al repositorio.

## Examples

- Un SHA explícito con política válida produce un manifiesto JSON reproducible.
- `HEAD` produce rechazo porque no demuestra aprobación independiente.
- Un SHA inexistente produce rechazo sin generar un baseline parcial.

## Do / Don't

- DO: guardar el manifiesto junto con la revisión humana que aprobó el SHA.
- DO: pasar el mismo SHA después a `verify_quality.py --approved-ref`.
- DON'T: sustituir el SHA por `HEAD` o por la rama actual.

## Tests

El oráculo congelado está en `tests/test_quality_baseline.py` y verifica hashes
de archivos protegidos y rechazo de referencias no explícitas.

## Constraints

- PARAR y reportar si el commit aprobado no contiene la política o algún protected.
- Este comando no crea commits ni modifica la configuración del repositorio.
