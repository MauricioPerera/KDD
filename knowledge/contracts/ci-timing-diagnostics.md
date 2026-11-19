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
tests_sha256: '8fa0d1376e2b6fe23e5d52fa248b57f71fe3bd6ed9fb47ab57975153c4e17b49'
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
directorios, nunca seguir enlaces simbolicos o puntos de reanalisis en
archivos o directorios. Los negativos de Windows deben cubrir junctions
sin exigir privilegios de symlink. La proteccion se aplica a archivos
quiescentes del job: no promete aislamiento ante otro proceso con los
mismos permisos que los sustituya concurrentemente.
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
un nombre Python punteado o la etiqueta exacta controller diagnostics que
el runtime usa para su propia salida. Conservar esa fila (tests_run cero)
sin publicar su stdout/stderr; no sumarla al coste de modulos como si fuera
trabajo adicional. scope debe ser product o infrastructure. Rows
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
- Vincular cada hash a las metricas del mismo recibo original. Para una
  fila de suite fallida conservar su codigo de salida exacto.
- Conservar duraciones exactas y hashes originales; no convertir failed,
  timeout, incomplete o falta de evidencia en aceptacion. La etiqueta run/SHA
  se proporciona desde el job y no autentica por si misma el origen del reporte.
- Agregar solamente Export CI timing diagnostics y Upload CI timing diagnostics
  como los dos ultimos pasos de validate, despues de todos los controles
  existentes, con export antes de upload y shell bash explicito para export
  en ambos sistemas. Un fallo de diagnostico queda visible en el resultado
  del job y no puede omitir controles previos. Pages conserva su requisito
  de un run exitoso para desplegar. Condicion export exacta:
  always() && !inputs.reusable_execution && github.repository == 'MauricioPerera/KDD'.
  Condicion upload: la misma conjuncion mas steps.ci-timings.outcome == 'success'.
  No sustituir AND por OR ni usar coincidencias de fragmentos como verificacion.
  Usar el pin upload-artifact ya vigente, nombre por
  run/attempt/OS, retencion 7 dias, overwrite false, if-no-files-found error.
- Publicar exclusivamente RUNNER_TEMP/kdd-ci-timings/timings.json. No subir
  kdd-command-reports o kdd-suite-reports crudos. Sin permisos nuevos.
- Conservar comandos de pruebas, workers, matrices, dos pasadas consecutivas,
  cobertura solo en la primera, SDK, post-init, Pages, runtime y protecciones.
  Sin continue-on-error, cache de evidencia o dependencias nuevas. El
  [reparto nativo](ci-windows-board-routing.md) define los jobs de union.

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
bundle por SHA explicito y ejecuta dos suites y un contrato genuinos, con
salida real al importar para ejercer la fila controller diagnostics. No
necesita historial upstream: debe funcionar tambien despues de init_project.
La proyeccion conserva exactamente las metricas de esos reportes y excluye
campos contaminados. Pruebas negativas cubren replay, runtime, JSON, datos
invalidos, claves duplicadas/version desconocida, rutas fuera de raiz,
salida existente, enlaces/junctions e identidad invalida. Solo el caso de
symlink de archivo POSIX tiene SKIP de aplicabilidad Windows; la prueba de
directorio redirigido se ejecuta en ambos sistemas. No cambiar SKIP previos.

El cableado exige los dos ultimos pasos de validate y conserva condiciones
nativas, upload fijado, archivo unico, comandos dual-OS y dos pasadas. Los
controles de evidencia rechazan intercambiar dos hashes de suite sin mover
sus metricas y convertir en cero el exit_code 1 de una fila de suite.
Ejecutar oraculos nuevos y vecinos localmente. Despues, dos pasadas por OS
en CI con inventarios y cobertura existentes. Publicar tres muestras del mismo candidato sin afirmar
ahorro antes de observarlo. No se exige una meta temporal para la telemetria.

## Constraints

Este baseline fortalece el contrato y los oraculos sobre el exportador
existente. El test_command debe seguir rojo por el orden previo del workflow
hasta aprobar y aplicar la correccion. El baseline conserva la implementacion.
Aplicar el [protocolo de revision](../baseline-risk-review.md) al SHA exacto
antes de implementar o tocar workflow. PARAR y reportar si requiere cambiar
runtime, protecciones, oraculos previos o las garantias de las dos pasadas.
La particion general y contratos en otros jobs necesitan contratos separados.

En el [reparto nativo](ci-windows-board-routing.md) los dos productores
Windows guardan diagnosticos parciales con nombre por rol. El rol full
conserva el nombre por SO en Ubuntu y en el flujo reutilizable.
La union publica el diagnostico Windows completo del intento. Preserva
el orden y los hashes de los tres sources y sus metricas exactas. Solo
se unen datos proyectados, desde los recibos del intento actual. No
cambia el formato de tiempos ni se usa como decision de aprobacion.
