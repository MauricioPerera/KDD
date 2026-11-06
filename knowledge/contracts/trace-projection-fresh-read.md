---
type: 'Task Contract'
title: 'Lectura fresca de modo y contenido en la proyeccion'
description: 'Consultar ambos datos juntos en el punto original de validacion, sin adelantar ni reutilizar pruebas.'
tags: ['traceability', 'git', 'performance', 'integration']
task: trace-projection-fresh-read
intent: 'Evitar un proceso Git por blob regular de la proyeccion manteniendo el orden y la frescura.'
target: scripts/traceability_git.py
signature: 'def blob(self, revision, name):'
test_command: 'python -m unittest tests.test_trace_projection_fresh_read'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_trace_projection_fresh_read.py
tests_sha256: 'ba18465883e20e526d03dbae6fa8f8d5fc316e18b774c6dd49bdcffdd179b885'
oracle_files: ['tests/test_trace_projection_fresh_read.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/traceability_git.py']
deps_allowed: ['stdlib', 'task_git', 'task_model', 'traceability_model', 'task_evidence', 'validate_tasks', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Reducir el coste de la [proyeccion Git](traceability-git.md) usando el lector
de metadatos ya disponible en [task_git](postinit-git-object-reads.md).
El [protocolo](../trace-projection-fresh-read.md) contiene evidencia y limites.

## Interface
Conservar _Projection.blob(revision, name), sus valores normalizados y los
errores del camino serial. Para un OID completo nativo, una ruta regular y
Git compatible, consultar modo y contenido en un solo proceso Git fresco
cuando ese par revision/ruta aun no esta en self.objects. La comprobacion
del formato nativo puede conservar su consulta existente por operacion.

## Invariants
- Usar el lector _read_metadata existente; no crear otro protocolo Git ni
  un proceso persistente. Validar el modo regular y el contenido del mismo
  resultado antes de guardar el valor en la proyeccion.
- Leer solo la ruta solicitada, en el punto donde blob la lee actualmente.
  No precargar tareas, producto, historia ni manifiestos para etapas futuras.
  No usar pruebas de modo o contenido anteriores de task_git como sustituto
  de esta observacion fresca. Conservar el cache existente de self.objects.
- Mantener valores LF, Unicode y vacios, SHA-1/SHA-256, rutas literales y
  las validaciones de exact_path. No leer archivos del checkout ni ejecutarlos.
- Para formato/entrada no compatible, modo no regular, ausencia o resultado
  ambiguo, conservar el camino serial y su primer error. Un error Git real
  no puede convertirse en un valor ni dejar un exito parcial en self.objects.
- Conservar los reemplazos tardios de nodo, producto, historia y manifiesto,
  las referencias moviles, enlaces, objetos corruptos y recuperacion.
- Mantener los 2107 IDs anteriores, Ubuntu/Windows, ambas suites, presupuesto
  seguro62 y limite600s. No cambiar otros oraculos, runtime ni workflows.

## Examples
- Un blob regular no observado: una lectura fresca de modo y contenido.
- Un enlace introducido despues de leer otra ruta: rechazar en la nueva lectura.
- Una lectura fallida y luego objeto restaurado: volver a consultar y recuperar.
- Git sin metadatos de modo compatibles: mismo valor o primer error serial.

## Do / Don't
- DO medir procesos reales con Trace2 y conservar las regresiones historicas.
- DON'T equiparar ahorro de procesos a cumplir480s sin medir el CI completo.

## Tests
El oraculo nuevo comprueba valores, modos, errores, recuperacion y lecturas
tardias con Git real. Los oraculos completos de trazabilidad y reemplazos
se ejecutan por separado, sin copiar sus casos a este archivo. El control
de fallback inyecta la senal de protocolo no compatible/ambiguo y exige
que el camino serial ejecute Git real; no simula sus bytes ni su resultado.

## Constraints
PARAR y reportar si falta el baseline revisado antes de implementar.
Revisar aparte cualquier cambio necesario de oraculo previo o runtime.
El objetivo sigue exigiendo tres CI completos consecutivos del mismo head
con init Windows<480s. Esta propuesta no cambia el head3655024 medido.
