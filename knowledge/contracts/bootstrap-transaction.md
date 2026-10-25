---
type: 'Task Contract'
title: 'Recuperar la inicializacion ante fallos de escritura'
description: 'Agrupar limpieza, reescrituras y guia en una transaccion con restauracion comprobable.'
tags: ['bootstrap', 'filesystem', 'integration']
task: bootstrap-transaction
intent: 'Conservar la copia original si falla una operacion recuperable del plan de inicializacion.'
target: scripts/bootstrap_transaction.py
language: python
signature: 'def filesystem_transaction(repo_dir, paths):'
test_command: 'python -m unittest tests/test_bootstrap_transaction.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 120
  params_max: 5
tests: tests/test_bootstrap_transaction.py
tests_sha256: '85300604e38dbbcc52dd778f4af040f6153e1c96466004f630516e0612035daa'
touch_only: ['scripts/bootstrap_transaction.py', 'scripts/init_project.py', 'scripts/bootstrap_project.py']
deps_allowed: ['stdlib']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Implementar la unidad de recuperacion del [protocolo](../bootstrap-safety.md)
sin duplicar el [manifiesto del inicializador](init-project.md).

## Interface

Context manager filesystem_transaction(repo_dir, paths) para nombres relativos
exactos. Valida/captura antes de yield; anidamiento de la misma raiz comparte
preimagenes. En error recuperable restaura el plan y propaga la excepcion
original. Un fallo de rollback se informa con BOOTSTRAP_ROLLBACK y no se oculta.

## Invariants

Guia incluida en preflight antes de limpiar. Al fallar, bytes, modos, mtime y
entradas originales del plan se conservan; sin temporales residuales ni cambios
en datos ajenos. Inicializador sigue delegandose una vez y conserva firmas,
resultados y codigos de CLI. El estado de transaccion no queda entre llamadas.

## Examples

- Guia existente como directorio: rechazo previo, proyecto intacto, reintento posible.
- Error real de IO tras borrar/escribir: restaurar preimagenes y propagar error.
- Region interna exitosa y fallo externo: restaurar ambas regiones.
- Exito: conservar los cambios del plan y los archivos ajenos.

## Do / Don't

- DO: usar fallos reales de filesystem y snapshots exactos.
- DON'T: tragar errores, ignorar cleanup, aumentar timeouts o usar sleeps/reintentos.

## Tests

tests/test_bootstrap_transaction.py usa las entradas reales para fallos
previsibles y el helper real con operaciones IO que fallan despues de cambios
parciales. No simula el resultado de init_project ni la restauracion.

## Constraints

No se afirma tolerancia a SIGKILL, power loss ni escritor hostil concurrente.
El fixture compartido esta sellado por bootstrap-filesystem-boundary.
PARAR y reportar si se necesita otro oraculo previo, runtime o proteccion.
