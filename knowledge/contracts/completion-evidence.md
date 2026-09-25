---
type: 'Task Contract'
title: 'Coherencia de cierre entre spec, reporte y evidencia'
description: 'Rechaza cierres nuevos con criterios pendientes, evidencia ausente o referencias de CI contradictorias; identifica explicitamente los cierres historicos.'
tags: ['kdd', 'specs', 'reports', 'evidence']
task: completion-evidence
intent: 'Un reporte no puede declarar verificacion en CI si el spec mantiene criterios pendientes o carece de evidencia coincidente.'
target: scripts/validate_completion.py
signature: 'def validate_completion(repo_root: str, policy_path: str = "completion-legacy.json", specs_dir: str = "specs") -> list:'
test_command: 'python -m unittest tests/test_validate_completion.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 300
  params_max: 4
tests: 'tests/test_validate_completion.py'
tests_sha256: '76d2df9967b9cf74f022cf03e77626f8ea7037b5f9f916ae795d09440e46db6a'
touch_only: ['scripts/validate_completion.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Cerrar la contradiccion descrita en [validacion](../validacion.md): un spec con
criterios pendientes no puede quedar verificado solo porque su reporte lo diga.
El validador lee specs, reportes y evidencia estructurada sin ejecutar codigo ni
consultar la red. La comprobacion del estado real del run de CI queda fuera de
esta capa local; el enlace al run es una referencia auditable, no un certificado.

## Interface

```python
def validate_completion(repo_root: str, policy_path: str = "completion-legacy.json", specs_dir: str = "specs") -> list:
    """Devuelve findings ordenados para los cierres de proyecto."""
```

CLI: `python scripts/validate_completion.py [--repo-root DIR] [--policy RUTA] [--specs-dir DIR]`.
Exit 0 sin errores; 1 si hay errores. El resumen separa PASS, FAIL y SKIP.

## Invariants

- Cada reporte `CONTRACT-NN-REPORT.md` debe corresponder a un unico spec.
- Un par historico puede ser SKIP solo si su digest coincide exactamente con
  `completion-legacy.json`; editar cualquiera de los dos exige migrarlo.
- Un cierre nuevo requiere checkboxes `- [x] [AC-1] ...` con IDs unicos y al
  menos un criterio `CI-*`; ningun checkbox puede quedar pendiente.
- Requiere `docs/reports/CONTRACT-NN-EVIDENCE.json` con `schema_version: 1`,
  `spec`, `state: verified_in_ci`, `ci.run_url`, `ci.head_sha` y un mapa
  `criteria` que coincida exactamente con los IDs del spec. Cada entrada tiene
  `status` (`locally_verified` o `verified_in_ci`) y `evidence` no vacia.
- Los criterios `CI-*` exigen `status: verified_in_ci` y evidencia igual al URL
  del run. El reporte debe contener ese mismo URL y la ruta del spec.
- Un URL de CI debe apuntar a un run de GitHub Actions del mismo repositorio
  declarado en la politica, con ID numerico. El SHA debe ser completo.
- La ausencia de un reporte deja el spec abierto; este gate no lo cierra.

## Examples

- Spec con `- [ ]` y reporte que dice "Ninguno pendiente" -> FAIL.
- Evidencia con un ID no presente en el spec -> FAIL.
- Reporte nuevo con checklist completo y evidencia coincidente -> PASS.
- Par historico de digest exacto -> SKIP, nunca PASS.

## Do / Don't

- DO: usar evidencia estructurada para comparar IDs y estado de cierre.
- DO: mantener los cierres historicos visibles como SKIP.
- DON'T: inferir que un enlace de CI prueba exito sin consultar su run.
- DON'T: ejecutar comandos de tests ni hacer solicitudes de red en este gate.

## Tests

`tests/test_validate_completion.py` cubre cierres coherentes, criterios
pendientes, IDs faltantes o sobrantes, URL y SHA invalidos, reporte huerfano,
legado intacto y legado editado.

## Constraints

- Mantener stdlib, lectura pura y rutas relativas al repositorio.
- El gate nuevo debe correr localmente y en el workflow reutilizable.
- PARAR y reportar si una migracion exige declarar verificado un criterio
  historico sin evidencia comprobable.
