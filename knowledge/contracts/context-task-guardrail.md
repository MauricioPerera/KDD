---
type: 'Task Contract'
title: 'Guardrail de tarea antes del recorte y salida segura'
description: 'Detectar patrones en la tarea completa y evitar que se publiquen en el reporte de contexto.'
tags: ['context', 'quality', 'security']
task: context-task-guardrail
intent: 'Detectar la tarea recortada y evitar que un hallazgo regex_deny divulgue texto rechazado.'
target: scripts/assemble_context.py
signature: 'def assemble(contract, task, base_dir):'
test_command: 'python -m unittest tests.test_context_task_guardrail'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_context_task_guardrail.py
tests_sha256: '530a6c1d7faa3d4f609c26594391a9a21304e5eceb90bd0daed90f095eb64825'
touch_only: ['scripts/assemble_context.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

El crecimiento de knowledge/index.md puede recortar la tarea antes de buscar
una credencial. Extender [assemble-context](assemble-context.md) para que
la deteccion de la tarea sea independiente del espacio que se le asigna.
El reporte de la CLI se usa como evidencia y tiene que ser seguro tambien
cuando el operador solicita contexto detallado.

## Interface

La CLI y assemble conservan los codigos. regex_deny inspecciona el contexto
final y, si ese chequeo no detecta un patron, inspecciona la tarea original.
Se busca cada patron en cada texto por separado. El patron encontrado en el
contexto final conserva precedencia. El diagnostico lo identifica por su
posicion de base uno en patterns, con el formato `patron matcheado: #N`.

## Invariants

- Un patron prohibido en la tarea original se informa aunque se recorte u
  omita todo el slot. En modo abort devuelve exit 2 y en modo report exit 0
  con el hallazgo. Emitir un solo hallazgo regex_deny por ensamblado.
- Conservar referencia, presupuesto, orden de slots, compactacion, manifest,
  patrones vigentes y deteccion sobre fuentes que llegaron al contexto.
- Cuando regex_deny detecta un patron, la CLI omite la tarea completa y la
  vista del contexto en stdout, tanto en modo abort como report, incluso
  con `--verbose`. Omitir el texto completo protege tambien ante patrones
  que solo identifican el prefijo de una credencial.
- En esa salida restringida conservar el presupuesto, las mediciones y los
  estados de los slots, la posicion del patron y un unico CONTEXT_MANIFEST
  con hashes, spans y estados reales. Omitir texto libre de otros hallazgos,
  rutas, errores de fuentes y nombres de nodos seleccionados u omitidos;
  mantener etiquetas fijas e IDs de slot declarados por la configuracion
  de confianza. El stderr de un aborto conserva la etiqueta de su causa y,
  cuando sea regex_deny, la posicion del patron. No emitir el patron como
  texto ni copiar fragmentos del contenido en ninguno de los dos flujos.
  En el manifiesto de la CLI, path pasa a null y se omite error en estos
  casos. Es la excepcion al [reporte completo](context-delivery-manifest.md)
  y a la vista habitual de verbose.
- Sin hallazgo regex_deny conservar el reporte habitual, los detalles de
  otras reglas, el manifiesto y la vista completa de `--verbose`. La API
  mantiene el contexto y el manifiesto completos para sus consumidores
  autorizados; la restriccion se aplica al mostrarlos.
- Conservar casos y cobertura anteriores y las dos pasadas en Ubuntu y Windows.

## Examples

- Una tarea con clave sintetica al final sigue bloqueada con el slot omitido.
- Una tarea inocua puede quedar omitida y seguir con exit 0.
- Con una credencial detectada, `--verbose` conserva el recibo estructurado
  y omite el cuerpo de contexto. En modo report el diagnostico sigue en
  stdout con exit 0.

## Do / Don't

- DO usar CLI y archivos reales.
- DON'T ampliar el presupuesto para que un caso concreto vuelva a caber.

## Tests

Ejecutar CLI con un presupuesto pequeno y una tarea recortada, con el slot
omitido y con un secreto presente en un nodo entregado. Verificar los modos
abort y report, y aceptar un control inocuo con el mismo presupuesto.
Comprobar la precedencia por posicion, un solo hallazgo y que la regex
no cruce textos. Ejecutar el proceso con un valor sintetico omitido,
recortado, visible, en una fuente y en un diagnostico de referencia.
Comprobar stdout y stderr con y sin verbose, patrones literales y de
prefijo y diagnosticos laterales. Comparar el recibo restringido con
un control que muestra nombres de nodos seleccionados, cortados y omitidos
y conserva su salida completa.

## Constraints

PARAR y reportar si se necesita cambiar configuracion, workflows, runtime o protecciones. La aprobacion
del baseline precede a la implementacion.
