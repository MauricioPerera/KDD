---
type: 'Task Contract'
title: 'Unir evidencia de contratos y suites Windows del mismo intento'
description: 'Verificar recibos autenticados para repartir el trabajo sobre los runners Windows existentes.'
tags: ['ci', 'performance', 'windows', 'integration']
task: ci-windows-board-receipts
intent: 'Cerrar el gate requerido solo con los dos productores del mismo intento y el inventario completo.'
target: .github/workflows/validate.yml
language: yaml
signature: 'Verify Windows validation receipts'
test_command: 'python -m unittest tests.test_ci_windows_board_receipts'
test_runner: python-unittest
test_scope: infrastructure
tests: tests/test_ci_windows_board_receipts.py
tests_sha256: '905ac66fcc5d2027114b73871c54f8484ac8420b0b130aa571cdf8118001db9c'
oracle_files: ['tests/test_ci_windows_board_receipts.py', 'tests/test_ci_trusted_execution.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
touch_only: ['scripts/ci_windows_join.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Mantener la [validacion confiable](ci-trusted-execution.md) y la evidencia
del [plazo de post-init](postinit-windows-common-deadline.md) cuando
contratos y suites se ejecutan en dos runners Windows ya presentes.

## Interface

El verificador stdlib acepta esta CLI. El workflow descarga cada ZIP
por ID y preserva sus bytes para verificar el digest.

    python -I scripts/ci_windows_join.py verify --repo-root DIR --runtime-bundle DIR --identity FILE --producers FILE --suite-inventory-sha256 SHA --contracts ZIP --suites ZIP --coverage ZIP

identity contiene repository, workflow, run_id, run_attempt, head_sha,
tree, runtime_ref y platform. Los dos IDs de Git se verifican contra
el checkout exacto. producers tiene entradas contracts, suites y
coverage, cada una con id entero positivo, digest SHA-256 hexadecimal
y result. Coverage y suites proceden de pasos distintos del mismo job.
El workflow materializa estos datos desde needs y su contexto actual.

Cada ZIP contiene un solo archivo regular, receipt.json en los dos
recibos y coverage.json en el artefacto de cobertura. Los recibos son
JSON sin claves duplicadas, con schema_version 1, role, identity, ok y
los datos del rol. Rutas inesperadas, miembros extra y enlaces fallan.
Cada recibo admite hasta 2 MiB comprimidos y 1 MiB descomprimido,
igual que post-init. Cobertura admite hasta 8 MiB comprimidos y
16 MiB descomprimidos. Aplicar los limites en un driver autocontenido,
sin cargar helpers del checkout sin revisar.
Los tres IDs de artefacto son distintos. El SHA-256 de cada ZIP coincide
con el digest del productor. Solo success acredita el job.

El recibo contracts agrega rows con los campos path POSIX relativo,
test_command, scope, shared_from, ok y exit_code. Cotejar su inventario
con el plan del gate fijado y su deduplicacion exacta desde el arbol
probado. Se agrupan los textos de comando exactos que usa el runtime
aprobado; no se introduce otra normalizacion. El recibo suites agrega
passes, dos filas ordenadas. Cada
fila contiene number, runtime, workers, expected_ids, executed_ids,
ok, errors, failures, fixture_omitted_ids y coverage.
La primera contiene coverage con pass_no=1, sha256, fragments,
lines_total y branches_total del reporte real. La segunda usa null.
Comparar los IDs ordenados de cada pasada (UTF-8, un ID por linea y
salto final LF) con el digest del discovery independiente del
productor Windows, ligado a su paso directo mediante needs. El
resumen de cobertura coincide con el reporte descargado del mismo intento, incluido su
SHA-256 de bytes y su identidad. Los tres ZIP se exigen aunque
la accion de descarga permita continuar habiendo encontrado uno.

La CLI devuelve 0 y JSON con ok=true solo con recibos validos. Rechaza
errores de identidad, transporte, esquema o inventario con exit 2.
Los recibos transportan solo los datos proyectados especificados y
los tiempos en el [formato existente](ci-timing-diagnostics.md).
No publican los reportes crudos del runner.

## Invariants

- Conservar cada comando y cada ID de las dos pasadas. Los inventarios
  esperados y ejecutados deben coincidir en ambas, sin duplicados,
  omisiones de fixture, errores ni fallos.
- Mantener el runtime revisado, cuatro workers del gate Windows, seis
  por pasada Windows, 600 s por comando y el init-project exclusivo.
- Mantener Ubuntu, consumidores reutilizables, cobertura de la primera,
  los dos recibos post-init y su plazo comun de 600 s, y Pages.
- Reutilizar el runner de Board Windows conservando su typecheck y sus
  pruebas. Un unico check requerido validate (windows-latest) refleja
  el resultado de los productores. No cambiar protecciones ni permisos.
- El check final se ejecuta ante un productor fallido, omitido o
  cancelado y falla de forma explicita. Solo el intento actual
  puede acreditarse. Los diagnosticos de tiempos no sustituyen
  evidencias de IDs, salida del productor ni cobertura.

## Examples

- Dos recibos del arbol, intento y runtime exactos con inventario
  completo y cobertura solo de la primera pasada pasan.
- Un ZIP del mismo SHA pero de otro intento falla incluso con su
  digest correcto.
- Un productor omitido, un caso faltante o una fila de contrato
  ausente bloquean el check.

## Do / Don't

- DO usar los outputs del paso fijado de upload-artifact y cotejar
  identidad y contenido con entradas esperadas del invocador.
- DON'T aceptar stdout, el nombre del ZIP, un check omitido, ni
  inferir el intento a partir de la fecha de los archivos.

## Tests

El oraculo crea un proyecto Git real, materializa el runtime externo,
ejecuta el comando del contrato y dos pasadas con el interprete real,
y usa esos datos para probar transporte, inventario e identidad.
Los IDs de upload y el resumen de cobertura del fixture se simulan.
La comprobacion alojada exige la cobertura real y la procedencia
de los productores del intento actual.

## Constraints

PARAR y reportar si se necesita publicar, cambiar el runtime fijado
o una proteccion. Revisar y aprobar previamente el baseline de
contratos/oraculos y luego el arbol exacto del workflow protegido.
La entrega exige tres CI comparables del mismo SHA con el trabajo
Windows completo, incluido el tiempo de cola y comprobacion final,
por debajo de la referencia en la medicion reproducible.
