---
type: 'Task Contract'
title: 'Atribucion verificable de los fallos de mutacion'
description: 'Distinguir aserciones de errores de ejecucion y conservar las fuentes, identidades y salidas de cada experimento.'
tags: ['oracles', 'mutation', 'governance']
task: mutation-attribution
intent: 'Impedir detecciones falsas tras controles sanos y conservar evidencia exacta.'
target: scripts/mutation_audit.py
signature: 'def audit_contract(contract_path, repo_root, timeout=120):'
test_command: 'python -m unittest tests.test_mutation_attribution'
budget:
  cyclomatic_max: 14
  nesting_max: 5
  lines_max: 220
  params_max: 3
tests: tests/test_mutation_attribution.py
tests_sha256: '4c204a1919809b7527dbd0a9bb9f1518ada9ded9ee2411ac0449199d87e61651'
touch_only: ['scripts/mutation_audit.py']
deps_allowed: ['stdlib', 'process_tree', 'validate_contracts', 'audit_seals']
forbids: ['network', 'llm']
---

## Intent

Aplicar la [garantia revisada de oraculos](../oracle-assurance.md), conservando
la [aprobacion de calidad](../quality-approval.md) y el
[objetivo de gobierno](../kdd-governance-closure.md).

## Interface

Conservar audit_contract, mutation_sources, CLI, operadores y conteos anteriores.
Agregar datos de evidencia sin borrar las claves existentes. Compartir la
clasificacion con la revision de contramuestras exactas del contrato de calidad.

## Invariants

- Controles original y copia sanos con pruebas realmente ejecutadas preceden mutantes.
- DETECTED requiere fallos de asercion reconocidos; importacion, OSError, salida
  sin pruebas, timeout o mezcla de errores quedan INCONCLUSIVE, nunca deteccion.
- SURVIVED requiere pruebas reconocidas ejecutadas y exitosas; cero pruebas no basta.
- Conservar fuente real mutante, hashes de target/oraculo/mutante, comando, exit,
  stdout, stderr, hash de salida y casos fallidos; no fabricar recibos del plan.
- No cambiar el checkout original ni ejecutar oraculos alli. Las copias usan
  process_tree existente; no se declara sandbox ni rollback de efectos hostiles.
- Mantener SKIP advisory de lenguajes/operadores no soportados. Un requisito de
  calidad no puede convertir ese SKIP en PASS.

## Examples

- Ambos controles pasan, mutante falla por ImportError -> tres INCONCLUSIVE.
- Aserciones reales rechazan los tres mutantes -> tres DETECTED con recibos.
- Aserciones ajenas pasan al ejecutar -> tres SURVIVED, sin fuerza inferida.

## Do / Don't

- DO medir procesos reales e identificar la fuente que efectivamente ejecutaron.
- DON'T contar una salida distinta de cero como demostracion del defecto.

## Tests

Nuevo oraculo tests/test_mutation_attribution.py: siete casos con el fixture
congelado de test_mutation_control_evidence, sin editarlo. Un registro externo
observa los hashes de las fuentes efectivamente leidas por los procesos.

## Constraints

PARAR y reportar si requiere otro archivo de produccion, otro oraculo, ampliar
budgets, bundle de tareas o cambiar workflows. El baseline incluye una revision
explicita de la semantica escrita en mutation-audit; su oraculo previo no cambia.
No implementar antes de aprobacion humana y CI dual-OS 2x de KG-2.
