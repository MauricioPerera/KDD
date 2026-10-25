---
type: 'Task Contract'
title: 'Validar workflows completos con motor fijado'
description: 'Instalar actionlint verificado y comprobar todos los YAML de workflows con diagnosticos reales y sin ejecutar sus pasos.'
tags: ['ci', 'syntax', 'integration']
task: workflow-syntax
intent: 'Detectar sintaxis y expresiones invalidas en cualquier workflow antes de fusionar.'
target: scripts/validate_workflows.py
language: python
signature: 'def validate_workflows(repo_root: str, binary: str | None = None) -> dict:'
test_command: 'python -m unittest tests/test_workflow_syntax.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 360
  params_max: 5
tests: tests/test_workflow_syntax.py
tests_sha256: '34acd2971114c65cfbea4de587031e153c5568f7350561b0768ea0de205a1c83'
touch_only: ['scripts/validate_workflows.py', 'tools/workflow-syntax/actionlint.json', 'scripts/guard_pr_baseline.py']
deps_allowed: ['stdlib', 'Git', 'actionlint@1.7.12', 'process_tree']
forbids: ['llm']
---

## Intent
Aplicar el [protocolo completo](../workflow-syntax-ci.md) y su limite de
[confianza](../verification-guarantees.md). El manifest es dependencia
revisada de este oraculo; el guard lo protege junto con el nuevo validador.

## Interface
CLI install/check y salida JSON conforme al protocolo. El cache externo
admite un archive oficial offline y exportacion GITHUB_ENV/PATH para CI.
Check recibe un proyecto y un binario opcional, verifica su hash y pasa todos
los workflows al motor real con configuracion externa vacia. Devuelve 0 solo
para PASS; los demas codigos del protocolo salen con exit 1.

## Invariants
Sin configuraciones/ignores del candidato, supresiones de reglas, shell,
ejecucion de run ni envios del YAML a servicios externos. Ningun caso ausente,
error de herramienta o cache incompatible se convierte en PASS/SKIP.
No modificar workflows, oraculos anteriores ni el runtime confiable.
Agregar solo las dos rutas nuevas a PROTECTED_FILES, preservando las previas.

## Examples
- Un deploy con colon+espacio sin bloque falla con archivo, linea y columna.
- El mismo comando en bloque literal o quoted pasa sin cambiar argumentos.
- Nuevo workflow .yaml malformado falla aunque no se dispare en el PR.
- Binario/cache cambiado falla antes de ejecutarse; config ignore no oculta errores.

## Do / Don't
- DO: usar procesos, repositorios Git y paquetes oficiales reales.
- DON'T: reemplazar el motor por mocks, regex de YAML, latest o binarios no verificados.

## Tests
tests/test_workflow_syntax.py contiene controles del motor, integraciones CLI,
cache/instalacion offline y dos commits reales por ruta protegida nueva.

## Constraints
Baseline humano de contratos, oraculos y manifest antes de implementar.
PARAR y reportar si hace falta otro runtime, oraculo previo o proteccion remota.
El budget es declarativo; no se afirma Nivel2 ni sandbox.
