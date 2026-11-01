---
type: 'Task Contract'
title: 'Dependencias reproducibles para compatibilidad CCDD'
description: 'Instala dependencias fijadas antes de ejecutar las pruebas de contexto en la matriz CI.'
tags: ['context', 'ci', 'dependencies']
task: context-v03-ci
intent: 'Verificar el adaptador real en Ubuntu y Windows sin omisiones.'
target: .github/workflows/validate.yml
signature: 'Install pinned context compatibility dependencies'
test_command: 'python -m unittest tests.test_context_v03'
budget:
  cyclomatic_max: 1
  nesting_max: 1
tests: 'tests/test_context_v03.py'
tests_sha256: '4725499368fe1b1ffb060faebc0a6fbbdc714598b456bf44fdbfe55f4ed9734e'
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['PyYAML', 'jsonschema']
forbids: ['llm']
---

## Intent
Aplicar el perfil de [dependencias y CI](../context-v03-compat.md).

## Interface
El workflow instala `tools/context-v03/requirements.txt` con hashes y wheels
antes de ejecutar contratos o suites; no agrega excepciones a la calidad.

## Invariants
- Ubuntu y Windows mantienen las dos pasadas y los checks anteriores.
- El proyecto inicializado conserva el paso y el lock.
- Una dependencia ausente o instalacion fallida no se convierte en SKIP/PASS.

## Examples
- Lock valido y dependencias disponibles -> integracion ejecutable.
- Lock o wheel no validos -> falla el paso antes de la suite.

## Do / Don't
- DO: verificar realmente el lock en ambos sistemas.
- DON'T: descargar dependencias desde el CLI de contexto.

## Tests
Los casos de `tests/test_context_v03.py` verifican orden y flujo del workflow.

## Constraints
PARAR y reportar si es necesario alterar una proteccion remota o el runtime confiable.
