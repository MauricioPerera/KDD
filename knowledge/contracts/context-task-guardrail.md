---
type: 'Task Contract'
title: 'Guardrail de tarea antes del recorte'
description: 'Conservar la deteccion de patrones de la tarea completa cuando se agota el presupuesto de contexto.'
tags: ['context', 'quality', 'security']
task: context-task-guardrail
intent: 'Evitar que el crecimiento de la KB oculte un patron prohibido de la tarea.'
target: scripts/assemble_context.py
signature: 'def assemble(contract, task, base_dir):'
test_command: 'python -m unittest tests.test_context_task_guardrail'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_context_task_guardrail.py
tests_sha256: 'f549677d34d88adfefcd62484ce56fce021a6f9e9ced296d8b834e063726da16'
touch_only: ['scripts/assemble_context.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

El crecimiento de knowledge/index.md puede recortar la tarea antes de buscar
una credencial. Extender [assemble-context](assemble-context.md) para que
la deteccion de la tarea sea independiente del espacio que se le asigna.

## Interface

La CLI y assemble conservan los codigos, formato y manifest. regex_deny
inspecciona el contexto final como antes y, si ese chequeo no detecta un
patron, inspecciona la tarea original. Se busca cada patron en cada texto
por separado. El patron encontrado en el contexto final conserva precedencia.

## Invariants

- Un patron prohibido en la tarea original se informa aunque se recorte u
  omita todo el slot. En modo abort devuelve exit 2 y en modo report exit 0
  con el hallazgo. Emitir un solo hallazgo regex_deny por ensamblado.
- Conservar referencia, presupuesto, orden de slots, compactacion, manifest,
  patrones vigentes y deteccion sobre fuentes que llegaron al contexto.
- El hallazgo describe el patron. No copiar el fragmento detectado a stderr.
- Conservar los oraculos anteriores y las dos pasadas en Ubuntu y Windows.

## Examples

- Una tarea con clave sintetica al final sigue bloqueada con el slot omitido.
- Una tarea inocua puede quedar omitida y seguir con exit 0.

## Do / Don't

- DO usar CLI y archivos reales.
- DON'T ampliar el presupuesto para que un caso concreto vuelva a caber.

## Tests

Ejecutar CLI con un presupuesto pequeno y una tarea recortada, con el slot
omitido y con un secreto presente en un nodo entregado. Verificar los modos
abort y report, y aceptar un control inocuo con el mismo presupuesto.
Comprobar la precedencia, un solo hallazgo y que la regex no cruce textos.

## Constraints

PARAR y reportar si se necesita cambiar configuracion, workflows, runtime o protecciones. La aprobacion
del baseline precede a la implementacion.
