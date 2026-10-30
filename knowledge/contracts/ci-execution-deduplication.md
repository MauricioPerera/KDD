---
type: 'Task Contract'
title: 'Reducir ejecuciones redundantes de CI'
description: 'Agrupar comandos identicos por invocacion y cancelar solo CI nativo superado del mismo PR, conservando matriz y suite 2x.'
tags: ['ci', 'verification', 'infra']
task: ci-execution-deduplication
intent: 'Reducir ejecuciones duplicadas sin reutilizar evidencia entre commits, sistemas operativos o pasadas de la suite.'
target: scripts/validate_test_commands.py
signature: 'def run_all(contracts_dir, repo_root, timeout=180, deduplicate=False) -> list'
test_command: 'python -m unittest tests/test_ci_optimization.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: 'tests/test_ci_optimization.py'
tests_sha256: '08cef80a0cb3e99a211e71047c2f83c0f8e56ff1a0bc9b5ac4fb5f9959ac3138'
touch_only: ['scripts/validate_test_commands.py', '.github/workflows/validate.yml']
deps_allowed: []
forbids: ['network', 'llm']
---

# Optimizacion conservadora de CI

## Intent

Extender [test-command-gate](test-command-gate.md) conservando las
[garantias de verificacion](../verification-guarantees.md) y la
[aprobacion independiente](../quality-approval.md).
Este contrato autoriza agregar `--deduplicate` al paso de comandos de
contratos y concurrencia al workflow; mantiene las dos pasadas dual-OS.

## Interface

La [extension de tiempo total](../ci-runtime.md) conserva esta agrupacion y
agrega workers optativo; las dos suites se ejecutan con el runner de
[procesos](ci-suite-processes.md), con los mismos IDs y comando/entorno
identicos en las dos pasadas. Sus oraculos anteriores conservan todas las
aserciones; solo se actualiza el comando esperado mediante baseline revisado.

- `run_all(..., deduplicate=False)` conserva por defecto una ejecucion por
  contrato. Con `True`, ejecuta una vez cada string `test_command` exactamente
  identico y distribuye su resultado a los contratos que lo declaran.
- Cada resultado conserva ruta, scope, comando, exit code, error y salida;
  agrega `shared_from` (ruta del primer contrato o `None`) y
  `duration_seconds` (tiempo real de esa ejecucion; cero para referencias).
- CLI `--deduplicate` activa la agrupacion. Reporta cada contrato y un resumen
  `Executions: contracts=N commands=M shared=K seconds=S`.
- El workflow agrega un input booleano `reusable_execution`, default `true`
  en `workflow_call`. Solo invocaciones nativas `pull_request`, sin ese
  input, comparten grupo por workflow y numero de PR y se cancelan al
  llegar otra ejecucion del mismo PR. Push y llamadas reutilizables usan
  grupos por `run_id` y `run_attempt`, sin cancelacion en curso.

## Invariants

- Solo strings identicos se agrupan; no inferir equivalencia de argumentos,
  espacios o cobertura. La tabla vive en UNA llamada, sin cache persistente.
- Todas las ejecuciones usan el mismo cwd, timeout y entorno heredado de esa llamada.
- Fallo, timeout o ejecutable ausente se propaga a TODOS los contratos
  asociados, respetando su scope; ninguna referencia se cuenta como SKIP.
- Orden por ruta; salida informativa. Solo exit code/error decide PASS/FAIL.
- Conservar validate y board en Ubuntu/Windows, Python 3.11, todos los gates,
  baseline independiente y las dos suites con comandos/entorno identicos.
- No cancelar push de main ni callers reutilizables; no equiparar el CI de
  PR con el posterior de main, que valida otra revision.

## Examples

- Dos contratos con `python verify.py`: una ejecucion con agrupacion y dos
  veredictos; sin el flag siguen siendo dos ejecuciones.
- Comando compartido termina en 3: ambos contratos FAIL y gate exit 1.
- Segunda llamada a `run_all`: ejecuta de nuevo aunque nada haya cambiado.

## Do / Don't

- DO: probar con procesos reales y un contador observable, incluyendo fallos.
- DO: medir antes/despues en serie, con mismo checkout/comandos/entorno;
  registrar muestras, exit codes, SHA, sistema y versiones de Python/Git.
- DON'T: comparar tiempos locales y alojados como si fueran equivalentes.
- DON'T: prometer ahorro global a partir de un unico comando repetido.

## Tests

Oraculo nuevo `tests/test_ci_optimization.py`: procesos reales, fallos
compartidos, timeout, comando ausente, llamadas independientes, default
compatible y diferencias de texto/entorno/cwd. Verifica las restricciones
de matriz, suites, gates y concurrencia en el workflow real.
Los oraculos anteriores conservan sus hashes.

## Constraints

Stdlib; sin dependencias nuevas, cache de evidencia, cambios de proteccion
de rama o baseline automatico. Registrar CI anterior por run/job; solo
afirmar medicion alojada posterior si realmente se ejecuta.
PARAR y reportar si se necesita cambiar un control de confianza protegido
para publicar; completar primero el diff revisable y la evidencia local.
