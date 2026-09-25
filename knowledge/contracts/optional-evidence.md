---
type: 'Task Contract'
title: 'Estados de evidencia opcional en CI'
description: 'Clasifica PASS, FAIL y SKIP de capas opcionales usando presencia de evidencia y resultado real del validador.'
tags: ['kdd', 'ci', 'evidence']
task: optional-evidence
intent: 'Un check verde no debe contar una capa ausente como verificada; las capas declaradas obligatorias deben fallar sin evidencia.'
target: scripts/optional_evidence.py
signature: 'def evaluate_layers(layers: list[str], required: set[str], environ: dict, summary: bool = False) -> list[dict]:'
test_command: 'python -m unittest tests/test_optional_evidence.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 180
  params_max: 4
tests: 'tests/test_optional_evidence.py'
tests_sha256: '3d08ae6316c800b58919c914a0650367d50682b94a82c0ea20479ad9c25d8cca'
touch_only: ['scripts/optional_evidence.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

La [validacion](../validacion.md) distingue la ausencia de evidencia de un
resultado comprobado. Este helper sirve a los workflows reutilizables y a la
accion compuesta: comprueba las capas que el consumidor declara obligatorias
y escribe un resumen de las capas opcionales en cada run.

## Interface

```python
def evaluate_layers(layers: list[str], required: set[str], environ: dict, summary: bool = False) -> list[dict]:
    """Devuelve una fila por capa con status y razon verificables."""
```

CLI: `python scripts/optional_evidence.py check|summary --layers LISTA`.
`KDD_REQUIRED_EVIDENCE` es una lista CSV de nombres de capas; las rutas y
los outcomes llegan por variables `KDD_*` del entorno, nunca como codigo de
shell. `summary` escribe tambien en `GITHUB_STEP_SUMMARY` cuando existe.

## Invariants

- Capas admitidas: security, compliance, privacy, accessibility,
  dependency-eol, observability, test-coverage y quality.
- Para las siete capas de scan, evidencia significa `findings.json` en la
  ruta declarada. Para quality, significa el archivo de politica declarado.
- `check`: capa requerida sin archivo -> FAIL; opcional ausente -> SKIP;
  presente -> PRESENT (todavia no significa que el validador paso).
- `summary`: archivo presente y validador success -> PASS; ausente y no
  requerido -> SKIP; requerido ausente o validador sin success -> FAIL.
- Un nombre de capa desconocido o requerido fuera de `--layers` falla.
- El script no ejecuta validadores ni interpreta rutas como comandos.

## Examples

- Sin `security/scan/findings.json` y sin requerir security -> SKIP.
- `KDD_REQUIRED_EVIDENCE=security` sin archivo -> FAIL antes del validador.
- Archivo presente, outcome failure -> FAIL; presente, success -> PASS.

## Do / Don't

- DO: usar outcomes reales de los pasos de CI en el resumen.
- DON'T: marcar PASS por mera existencia del archivo.
- DON'T: interpretar SKIP como aprobacion de calidad o seguridad.

## Tests

`tests/test_optional_evidence.py` cubre ausencia opcional, evidencia
obligatoria ausente, success/failure/skipped, quality y nombres invalidos.

## Constraints

- Python stdlib, sin red ni procesos externos.
- PARAR y reportar si el workflow no puede distinguir el outcome de una
  capa; no convertir un paso no ejecutado con evidencia presente en PASS.
