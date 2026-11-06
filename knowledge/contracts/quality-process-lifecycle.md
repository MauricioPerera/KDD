---
type: 'Task Contract'
title: 'Checks de calidad contenidos con runtime aprobado'
description: 'Cerrar descendientes propios antes del veredicto de integridad y de la devolucion del runner.'
tags: ['quality', 'processes', 'integration']
task: quality-process-lifecycle
intent: 'Impedir escrituras tardias de checks y conservar el helper desde la referencia humana.'
target: scripts/verify_quality.py
language: python
signature: 'def approve(root, policy_path, reference):'
test_command: 'python -m unittest tests/test_quality_process_lifecycle.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 160
  params_max: 5
tests: tests/test_quality_process_lifecycle.py
tests_sha256: 'bfaef9718e62427abf99076d395f69c62cbff6049cd0d6f1a72a4eb6ede2255a'
touch_only: ['scripts/verify_quality.py']
deps_allowed: ['stdlib', 'process_tree']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [protocolo de correccion](../audit-quality-cache-onboarding.md)
y la [aprobacion humana](../quality-approval.md).

## Interface
Conservar approve, CLI, politica, argv, salida y dos rondas. Extraer el helper
regular scripts/process_tree.py desde reference a temporal externo, sin otra
referencia ni import de codigo candidato. No cambiar la API de process_tree.

## Invariants
Exito, fallo y timeout contienen y esperan procesos propios antes de volver a
comprobar integridad. Un error rechaza. Helpers faltantes o con modo Git no
regular fallan antes de checks; 100644/100755 se aceptan. Conservar vecinos,
perimetro, politica y oraculos, timeout, gracia compartida y limites declarados.
Mantener treinta procesos Git en el fixture de batching existente.

## Examples
- Check lanza hijo/nieto y termina: ninguna escritura posterior a la devolucion.
- Timeout rechaza y contiene el arbol; un vecino ajeno completa su trabajo.
- Runner extraido solo: usa helper de Git aprobado, aun con helper local alterado.

## Do / Don't
- DO: readiness y procesos reales, evidencia antes/despues y limpieza propia.
- DON'T: cargar helper candidato, relajar timeout o presentar contencion como sandbox.

## Tests
tests/test_quality_process_lifecycle.py usa repositorios, politica y procesos
reales, dos rondas, modos de indice y runner externo. No simula Git o procesos.
El [observador de identidad](quality-process-observer.md) retiene los objetos
antes de confirmar readiness y conserva los doce metodos y sus aserciones.
El [protocolo](../process-observer-identity.md) distingue este ajuste del oraculo
de una correccion del runtime y conserva la evidencia del fallo original.

## Constraints
PARAR y reportar si se necesita adoptar otro baseline o cambiar el runtime
aprobado, un workflow o una proteccion remota.
Baseline nuevo revisado antes de implementar. No modificar process_tree.py,
runtime de CI, workflows, variables remotas ni protecciones. El fixture legado
y su sello solo cambian en el baseline presentado a revision.
