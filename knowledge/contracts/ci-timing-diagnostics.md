---
type: 'Task Contract'
title: 'Publicacion de diagnostico de tiempos sin cambiar la ejecucion de CI'
description: 'Proyectar duraciones de modulos y contratos del runtime existente en un artefacto sin salidas privadas.'
tags: ['ci', 'performance', 'diagnostics', 'integration']
task: ci-timing-diagnostics
intent: 'Publicar el coste observado por modulo y contrato para decidir el siguiente reparto del CI.'
target: .github/workflows/validate.yml
language: yaml
signature: 'Export CI timing diagnostics'
test_command: 'python -m unittest tests.test_ci_timing_diagnostics tests.test_ci_timing_workflow'
test_runner: python-unittest
test_scope: infrastructure
tests: tests/test_ci_timing_diagnostics.py
tests_sha256: '719220011221ad70876c518dc5de77a3dcbed334b5b219faf99677793e5cfb09'
oracle_files: ['tests/test_ci_timing_diagnostics.py', 'tests/test_ci_timing_workflow.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
touch_only: ['scripts/ci_timings.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib', 'git', 'PyYAML']
forbids: ['network', 'llm']
---

## Intent

Aplicar la [primera entrega de diagnostico](../ci-timing-diagnostics.md)
sin alterar la [ejecucion confiable](ci-trusted-execution.md), cobertura,
inventarios, oraculos existentes ni [aprobaciones](../quality-approval.md).

## Interface

Nuevo CLI stdlib, ejecutado desde el checkout:

```text
python -I scripts/ci_timings.py export --repo-root . --commands-dir DIRECTORIO --suites-dir DIRECTORIO --output ARCHIVO --run-id NUMERO --run-attempt NUMERO --head-sha OID --platform SO --trusted-runtime-ref OID
```

Leer solo archivos regulares evidence-*.json del nivel inmediato de ambos
directorios, nunca seguir enlaces simbolicos en archivos o directorios.
Conservar los bytes originales. Admitir cero o un reporte commands y cero,
uno o dos reportes suite; mas es ambiguo. Ausencia de directorio equivale
a cero reportes para ese tipo. No buscar archivos alternativos ni interpretar
salidas del producto como metricas. JSON invalido, claves duplicadas, version
distinta de 1, runtime distinto o campos metricos invalidos son error.

Salida con claves exactas schema_version=1, kind=kdd-ci-timings, identity,
complete, missing, sources. identity tiene run_id y run_attempt enteros
positivos, head_sha y trusted_runtime_ref OID lowercase de 40 hex, platform
ubuntu-latest o windows-latest. sources se ordena por (kind, source_sha256),
sin atribuir numero de pasada por nombre de archivo, fecha o duracion.

Cada source contiene solo kind (commands/suite), source_sha256 (SHA-256 de
bytes originales), recorded_ok booleano, duration_seconds y rows. Cada fila
suite contiene solo module, duration_seconds, tests_run y exit_code. Cada
fila commands contiene solo contract, scope, duration_seconds, exit_code,
recorded_ok y shared_from. Normalizar rutas contract y shared_from a POSIX
relativas al repo-root; rechazar rutas fuera del checkout. module debe ser
un nombre Python punteado. scope debe ser product o infrastructure. Rows
ordenadas por duracion descendente y luego etiqueta ascendente; no truncar.

Duraciones finitas no negativas, nunca bool/null en campos numericos
requeridos; tests_run entero no negativo, exit_code entero o null. Los
booleanos no son enteros. duration_seconds del source commands es null:
la suma de comandos paralelos no es tiempo de pared. Compartidos conservan
shared_from y cero segundos. Reportes suite con hash repetido son replay.

complete solo indica presencia de uno y dos reportes: NO significa PASS.
missing ordena commands-report, suite-report-1, suite-report-2 segun las
cantidades ausentes. Un reporte presente fallido puede proyectarse sin
alterar recorded_ok/exit_code. Una estructura sin las metricas requeridas
falla; no inventar ceros, omitir filas o publicar parcialmente.

Exit 0 al publicar diagnostico completo o explicitamente incompleto. Exit 2
en error, mensaje generico sin volcar contenido/paths arbitrarios y sin JSON
de salida. Nunca sobrescribir una salida existente ni dejar archivo parcial.
Crear el padre del output si falta. No ejecutar codigo o comandos del reporte.

## Invariants

- Publicar solo el esquema permitido. No copiar stdout, stderr, error libre,
  entorno, comandos, rutas absolutas o campos adicionales del reporte.
- Conservar duraciones exactas y hashes originales; no convertir failed,
  timeout, incomplete o falta de evidencia en aceptacion. La etiqueta run/SHA
  se proporciona desde el job y no autentica por si misma el origen del reporte.
- Agregar solamente Export CI timing diagnostics y Upload CI timing diagnostics
  a validate, despues de las dos suites. Native MauricioPerera/KDD, always(),
  sin habilitarlo en callers reutilizables. El upload corre solo si el export
  termino con success; usar el pin upload-artifact ya vigente, nombre por
  run/attempt/OS, retencion 7 dias, overwrite false, if-no-files-found error.
- Publicar exclusivamente RUNNER_TEMP/kdd-ci-timings/timings.json. No subir
  kdd-command-reports o kdd-suite-reports crudos. Sin permisos nuevos.
- Conservar comandos de pruebas, workers, matrices, dos pasadas consecutivas,
  cobertura solo en la primera, SDK, post-init, Pages, runtime y protecciones.
  Sin continue-on-error, otros jobs, cache de evidencia o dependencias nuevas.

## Examples

- Reportes reales completos: tres sources con tiempos por fila y sus hashes.
- El pipeline fallo antes de la segunda suite: complete false y missing
  suite-report-2; los controles previos conservan su propio fallo.
- Dos archivos con el mismo reporte suite: exit 2 y ningun artefacto nuevo.
- stdout contiene una metrica falsificada: no aparece en el JSON publicado.

## Do / Don't

- DO usar un artefacto nuevo por job; el diagnostico no decide otros checks.
- DON'T sumar tiempo concurrente como latencia, inferir CPU no medida o
  prometer una reduccion por publicar esta primera entrega.

## Tests

Oraculos nuevos de diagnostico y cableado; ningun test previo cambia. El
fixture crea un Git local con los archivos actuales del runtime, prepara un
bundle por SHA explicito y ejecuta dos suites y un contrato genuinos. No
necesita historial upstream: debe funcionar tambien despues de init_project.
La proyeccion conserva exactamente las metricas de esos reportes y excluye
campos contaminados. Pruebas negativas cubren replay, runtime, JSON, datos
invalidos, rutas fuera de raiz, salida existente e identidad invalida.

El cableado verifica ubicacion, condiciones nativas, upload fijado y archivo
unico, conservando comandos dual-OS y dos pasadas. Ejecutar oraculos nuevos
y vecinos localmente; despues dos pasadas por OS en CI con inventarios y
cobertura existentes. Publicar tres muestras del mismo candidato sin afirmar
ahorro antes de observarlo. No se exige una meta temporal para la telemetria.

## Constraints

Este commit solo propone contrato y oraculos; el target nuevo no esta
implementado y el test_command debe seguir rojo por esa ausencia.
Aplicar el [protocolo de revision](../baseline-risk-review.md) al SHA exacto
antes de implementar o tocar workflow. PARAR y reportar si requiere cambiar
runtime, protecciones, oraculos previos o las garantias de las dos pasadas.
La particion general y contratos en otros jobs necesitan contratos separados.
