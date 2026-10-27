---
type: 'Task Contract'
title: 'Controles originales y de copia antes de medir mutantes'
description: 'Evitar detecciones falsas por importaciones rotas o dependencias perdidas en la copia de mutacion.'
tags: ['mutation', 'quality', 'integration']
task: mutation-control-evidence
intent: 'Medir mutantes solo despues de controles originales y de copia verdes.'
target: scripts/mutation_audit.py
language: python
signature: 'def audit_contract(contract_path, repo_root, timeout=120):'
test_command: 'python -m unittest tests/test_mutation_control_evidence.py'
budget:
  cyclomatic_max: 18
  nesting_max: 5
  lines_max: 220
  params_max: 5
tests: tests/test_mutation_control_evidence.py
tests_sha256: '3fd63e1472dfb7d8208cb0c36d1425bcdd8e44be618cb63cdc6f506f598c0831'
touch_only: ['scripts/mutation_audit.py']
deps_allowed: ['stdlib', 'process_tree']
forbids: ['network', 'llm']
---

## Intent
Aplicar [controles de mutacion](../audit-remediation-approval-mutation-board.md)
y la distincion de evidencia de [calidad](../quality-approval.md).
## Interface
Conservar audit_contract, CLI, claves y operadores existentes. Agregar controles
original/copy con status, exit_code y timeout; FAIL sin ejecutar mutantes si fallan.
## Invariants
- Exigir original y copia sin mutar verdes en temporales externos antes de operadores.
- Un fallo de preparacion o control no suma DETECTED; --strict falla.
- Conservar helpers .agents, oraculo y working tree original sin cambios.
- No ejecutar oraculos en el working tree real.
- Conservar SURVIVED, timeout INCONCLUSIVE, no Python/no operador SKIP y conteos.
- Las ejecuciones usan la contencion existente; no cambiar ese helper.
## Examples
- Original con ImportError -> FAIL y cero mutantes/detecciones.
- Test ajeno al target con helper .agents -> SURVIVED, no falso DETECTED.
## Do / Don't
- DO: ejecutar unittest y CLI reales con controles positivos e inconclusos.
- DON'T: simular retornos o contar una copia rota como deteccion.
## Tests
El oraculo nuevo cubre controles, fidelidad de copia, mutantes reales, fallos,
timeout y salida estricta, sin alterar los tres casos anteriores.
## Constraints
PARAR y reportar si requiere modificar oraculos previos, runtime, workflows,
locks o protecciones. Cambiar contrato y baseline solo mediante revision humana.
