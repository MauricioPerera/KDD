---
type: 'Task Contract'
title: 'Verificacion remota del run que respalda un cierre de proyecto'
description: 'Confirma que la evidencia de cierre enlaza un run de validacion completo y exitoso para el SHA declarado, sin permitir autocertificacion.'
tags: ['kdd', 'ci', 'evidence']
task: verify-completion-runs
intent: 'Un cierre verified_in_ci requiere un run previo de GitHub Actions exitoso para el codigo entregado.'
target: scripts/verify_completion_runs.py
signature: 'def verify_run(evidence: dict, repository: str, current_run_id: int, fetch_run) -> list:'
test_command: 'python -m unittest tests/test_verify_completion_runs.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 300
  params_max: 5
tests: 'tests/test_verify_completion_runs.py'
tests_sha256: '764cb956b203af952aa184697e230b2ee31145bca2c4cd3e963a71a9b762526d'
touch_only: ['scripts/verify_completion_runs.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent

Complementar el validador local de cierre sin introducir red en
`scripts/validate_completion.py`. El run de CI enlazado por el manifiesto es
anterior al cierre: primero se valida el commit de implementacion; luego un
commit de cierre agrega el reporte y la evidencia de ese run. El workflow del
commit de cierre consulta GitHub y rechaza un run en curso, fallido, ajeno o
correspondiente a si mismo.

## Interface

`verify_run(evidence, repository, current_run_id, fetch_run, workflow_path='.github/workflows/validate.yml')`
devuelve findings con claves `rule` y `msg`. `fetch_run(repository, run_id)`
devuelve el objeto JSON del endpoint de GitHub Actions o lanza un error.

`verify_closure_diff(changed_paths)` devuelve findings para cualquier archivo
modificado despues del SHA validado que no sea el spec, reporte, manifiesto de
evidencia o `CHANGELOG.md` de un contrato de ejecucion.

CLI: `python scripts/verify_completion_runs.py --repository OWNER/REPO
--current-run-id ID --candidate-sha SHA [--repo-root DIR]
[--workflow-path .github/workflows/validate.yml]`. Lee `GITHUB_TOKEN` del
entorno; no recibe ni imprime el token. Procesa los manifiestos de evidencia
de cierres nuevos y falla cerrado ante errores de Git, API o JSON. Sin cierres
nuevos termina en PASS sin llamadas remotas.

## Invariants

- Solo `https://api.github.com/repos/OWNER/REPO/actions/runs/ID` se consulta;
  OWNER/REPO e ID provienen de una URL de evidencia validada contra el
  repositorio de CI. No se siguen URL arbitrarias del reporte.
- El objeto remoto debe tener `status: completed`, `conclusion: success`,
  `head_sha` igual al manifiesto, `repository.full_name` igual al repositorio,
  `html_url` igual al enlace y workflow de validacion esperado. La respuesta
  ausente o ilegible no equivale a exito.
- `current_run_id` no puede ser el run certificado, aunque la API devuelva
  un estado inesperado.
- El SHA del run debe ser ancestro del commit candidato. Su diff hasta el
  candidato solo puede contener archivos de cierre (`specs/CONTRACT-*.md`,
  `docs/reports/CONTRACT-*-REPORT.md`, `docs/reports/CONTRACT-*-EVIDENCE.json`,
  `CHANGELOG.md`). Un cambio posterior de codigo u oraculos exige otro run.
- El token necesita solo `actions: read`; no se ejecuta codigo del run citado.

## Examples

- Run anterior exitoso, mismo repositorio, SHA y workflow; solo cambia el
  cierre -> PASS.
- Run en curso, fallido, ajeno, con otro SHA o el run actual -> FAIL.
- URL de un workflow sin validacion o codigo modificado tras el run -> FAIL.
- Proyecto sin cierres nuevos -> PASS sin consulta a GitHub.

## Tests

`tests/test_verify_completion_runs.py` prueba aceptacion, estados remotos,
identidad del repositorio, SHA, workflow, autocertificacion, fallo de API y
diff permitido. No accede a la red.

## Do / Don't

- DO: autenticar el run anterior con la API de GitHub desde el workflow.
- DO: mantener separada la validacion local, que sigue siendo sin red.
- DON'T: aceptar una URL o un estado declarados solo por el reporte.

## Constraints

- Mantener stdlib y tiempo de espera acotado para API y Git.
- No registrar credenciales ni aceptar redireccionamientos a un host ajeno.
- No consultar el resultado del run actual; el modelo es de dos commits.
- PARAR y reportar si la API no permite confirmar el run referenciado.
