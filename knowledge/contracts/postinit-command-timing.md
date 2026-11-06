---
type: 'Task Contract'
title: 'Evidencia del tiempo completo de init en CI'
description: 'Publicar la duracion existente del runtime revisado sin confundirla con el lote o stdout del producto.'
tags: ['ci', 'performance', 'bootstrap', 'integration']
task: postinit-command-timing
intent: 'Medir la aceptacion de margen Windows sobre la invocacion completa de init-project.'
target: .github/workflows/validate.yml
language: yaml
signature: 'Report init command duration'
test_command: 'python -m unittest tests.test_postinit_command_timing'
budget:
  cyclomatic_max: 1
  nesting_max: 1
tests: tests/test_postinit_command_timing.py
tests_sha256: '48f8aedb1329c062a9d50102d7736fdc1bdeaa3378229e0222aea1945f6900ea'
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['GitHub Actions', 'Python3.11']
forbids: ['llm']
---

## Intent
Observar el [objetivo de margen](../postinit-windows-runtime.md) usando
duration_seconds de la [ejecucion revisada](ci-execution-deduplication.md),
que ya incluye arranque, proceso y limpieza del comando entero.

## Interface
Agregar a validate el paso Python `Report init command duration`, despues de
los comandos de contrato y antes de las dos suites. Correr siempre en los runs
nativos de MauricioPerera/KDD, sin activarlo para callers reusable.
Leer el unico evidence-*.json de RUNNER_TEMP/kdd-command-reports, seleccionar
el resultado exacto del contrato knowledge/contracts/init-project.md y emitir
una unica linea KDD_INIT_TIMING seguida de JSON, con schema_version=1,
run_id, run_attempt, head_sha, trusted_runtime_ref, contract, duration_seconds,
ok, exit_code y error. Copiar los valores del resultado, nunca medir solo el
child interno ni inferirlos de stdout.

## Invariants
- Falta, duplicidad o JSON invalido en el reporte es fallo de evidencia.
  Rechazar runtime distinto del KDD_TRUSTED_RUNTIME_REF esperado, versiones
  desconocidas y resultados de init ausentes, duplicados o compartidos.
- Exigir el comando de init actual y scope infrastructure; la duracion es un
  numero finito no negativo, no bool. ok es bool; no transformar timeout o
  exit no cero en exito al publicarlo.
- Los datos identifican el run, intento y SHA del entorno de GitHub. Publicar
  solo el resumen declarado, sin stdout/stderr ni variables arbitrarias.
- head_sha corresponde a GITHUB_SHA, el checkout de GitHub (merge de PR si
  corresponde). El head candidato se coteja con los metadatos del workflow run;
  no confundir ese candidato con el OID sintetico de merge.
- Conservar permisos, pins, runtime, matriz, dos pasadas y timeout 600. No
  agregar continue-on-error, filtros de pruebas, jobs, servicios ni un runner.

## Examples
- El comando real pasa: la linea publica su duracion y estado del reporte.
- El comando real falla: se conserva ok=false y el exit real en la evidencia.
- El producto imprime una metrica falsa: su stdout no decide el resumen.

## Do / Don't
- DO reutilizar el campo de duracion calculado por el runtime revisado.
- DON'T confundir la suma del lote, tiempo de unittest o una repeticion fallida con aceptacion.

## Tests
El oraculo ejecuta el gate y un unittest reales en un Git temporal, y despues
ejecuta el bloque Python extraido del workflow. Verifica exito, fallo, un
stdout falsificado, evidencia ausente/ambigua y datos invalidos.

## Constraints
Baseline humano antes de implementar el workflow. PARAR y reportar si se
requiere cambiar runtime o protecciones; esta entrega no autoriza excepciones.
